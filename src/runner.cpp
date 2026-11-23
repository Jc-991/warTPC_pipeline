// Warwick TPC runner: builds the `charge` and `optical` executables.
//
//   charge  -i <dataset> -o <output_dir>   -> runs charge_run.sh
//   optical -i <dataset> -o <output_dir>   -> runs optical_run.sh
//
// The Blackbox shell scripts write into the dataset they are given, so the
// runner first mirrors the dataset into <output_dir> and runs the unchanged
// script on that mirror. The input dataset is never written to.
//
// WARTPC_MODE ("charge" or "optical") is set per executable by CMake.

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <set>
#include <sstream>
#include <string>
#include <sys/wait.h>
#include <vector>

#if defined(__APPLE__)
#include <mach-o/dyld.h>
#endif

#ifndef WARTPC_MODE
#error "WARTPC_MODE must be defined (charge or optical)"
#endif

namespace fs = std::filesystem;

namespace {

struct Mode {
    std::string name;
    std::string script;               // Blackbox shell script to run
    std::vector<std::string> tools;   // files the script expects in its cwd
    std::string data_subdir;          // dataset subfolder holding the runs
    std::set<std::string> generated;  // per-run outputs: never mirrored, so
                                      // the script cannot write through a link
    std::string done_marker;          // per-run file that marks success
};

Mode current_mode() {
    const std::string m = WARTPC_MODE;
    if (m == "optical")
        return {"optical", "optical_run.sh", {"tpx3dump", "optical-analysis.py"}, "optical",
                {"output.hdf5", "integral.csv", "integral-inspect.csv",
                 "signal-integral.csv", "signal-integral_raw.csv"},
                "integral.csv"};
    return {"charge", "charge_run.sh", {"waveform-integrator.py", "waveform-plotting.py"}, "charge",
            {"waveforms.root", "signal.csv", "signal-inspect.csv"},
            "signal.csv"};
}

// Large read-only inputs are symlinked; everything else is copied.
bool link_instead_of_copy(const fs::path& p) {
    return p.extension() == ".tpx3" || p.filename() == "waveforms.csv";
}

std::string shell_quote(const std::string& s) {
    std::string out = "'";
    for (char c : s) out += (c == '\'') ? std::string("'\\''") : std::string(1, c);
    return out + "'";
}

std::string timestamp(const char* fmt) {
    std::time_t t = std::time(nullptr);
    char buf[64];
    std::strftime(buf, sizeof buf, fmt, std::localtime(&t));
    return buf;
}

fs::path executable_dir(const char* argv0) {
    std::error_code ec;
#if defined(__linux__)
    fs::path p = fs::read_symlink("/proc/self/exe", ec);
    if (!ec) return p.parent_path();
#elif defined(__APPLE__)
    char buf[4096];
    uint32_t size = sizeof buf;
    if (_NSGetExecutablePath(buf, &size) == 0) return fs::weakly_canonical(buf, ec).parent_path();
#endif
    return fs::weakly_canonical(fs::absolute(argv0), ec).parent_path();
}

bool has_all(const fs::path& dir, const Mode& m) {
    if (!fs::is_regular_file(dir / m.script)) return false;
    for (const auto& t : m.tools)
        if (!fs::is_regular_file(dir / t)) return false;
    return true;
}

// --blackbox, then $WARTPC_BLACKBOX, then the installed share dir, then the source tree.
fs::path find_blackbox(const std::string& cli, const fs::path& exe_dir, const Mode& m) {
    std::vector<fs::path> candidates;
    if (!cli.empty()) return fs::absolute(cli);
    if (const char* env = std::getenv("WARTPC_BLACKBOX")) return fs::absolute(env);
    candidates.push_back(exe_dir.parent_path() / WARTPC_REL_DATADIR);
    candidates.push_back(WARTPC_SOURCE_DIR);
    for (const auto& c : candidates)
        if (has_all(c, m)) return c;
    return candidates.back();
}

bool is_within(const fs::path& child, const fs::path& parent) {
    auto c = child.begin();
    for (auto p = parent.begin(); p != parent.end(); ++p, ++c)
        if (c == child.end() || *p != *c) return false;
    return true;
}

std::vector<std::string> run_dirs(const fs::path& dir) {
    std::vector<std::string> runs;
    if (!fs::is_directory(dir)) return runs;
    for (const auto& e : fs::directory_iterator(dir))
        if (e.is_directory() && e.path().filename() != "results")
            runs.push_back(e.path().filename().string());
    std::sort(runs.begin(), runs.end());
    return runs;
}

// Mirror the top-level files of one run folder. Subfolders are earlier
// generated results and are skipped; the scripts recreate them.
void mirror_run(const fs::path& src, const fs::path& dst, const Mode& m) {
    fs::create_directories(dst);
    for (const auto& e : fs::directory_iterator(src)) {
        if (!e.is_regular_file()) continue;
        const fs::path name = e.path().filename();
        if (m.generated.count(name.string())) continue;
        const fs::path target = dst / name;
        if (fs::is_symlink(fs::symlink_status(target)) || fs::exists(target)) fs::remove(target);
        if (link_instead_of_copy(name))
            fs::create_symlink(fs::canonical(e.path()), target);
        else
            fs::copy_file(e.path(), target);
    }
}

void usage(const Mode& m) {
    std::cout <<
        "Usage: " << m.name << " -i <dataset> -o <output_dir> [options]\n\n"
        "Runs the Blackbox " << m.script << " on a mirror of <dataset> built in\n"
        "<output_dir>. The dataset itself is never modified.\n\n"
        "  -i, --input DIR     dataset folder containing " << m.data_subdir << "/<run>/\n"
        "  -o, --output DIR    where results are written (created if missing)\n"
        "  --blackbox DIR      folder with " << m.script << " and its tools\n"
        "                      (default: $WARTPC_BLACKBOX, else the bundled copy)\n"
        "  --setup FILE        environment script to source first, e.g. setup_blackbox.sh\n"
        "                      (default: $BLACKBOX_SETUP, else the bundled one when a\n"
        "                      'module' system is present)\n"
        "  --no-setup          do not source any environment script\n"
        "  -h, --help          show this help\n";
}

}  // namespace

int main(int argc, char** argv) {
    const Mode m = current_mode();
    std::string in_arg, out_arg, blackbox_arg, setup_arg;
    bool no_setup = false;

    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        auto value = [&](const char* flag) -> std::string {
            if (i + 1 >= argc) { std::cerr << m.name << ": " << flag << " needs a value\n"; std::exit(2); }
            return argv[++i];
        };
        if (a == "-h" || a == "--help") { usage(m); return 0; }
        else if (a == "-i" || a == "--input") in_arg = value("-i");
        else if (a == "-o" || a == "--output") out_arg = value("-o");
        else if (a == "--blackbox") blackbox_arg = value("--blackbox");
        else if (a == "--setup") setup_arg = value("--setup");
        else if (a == "--no-setup") no_setup = true;
        else { std::cerr << m.name << ": unknown argument '" << a << "'\n\n"; usage(m); return 2; }
    }
    if (in_arg.empty() || out_arg.empty()) { usage(m); return 2; }

    try {
        const fs::path input = fs::canonical(in_arg);
        const fs::path output = fs::weakly_canonical(fs::absolute(out_arg));
        const fs::path src_runs = input / m.data_subdir;

        if (!fs::is_directory(src_runs)) {
            std::cerr << m.name << ": " << src_runs << " not found; the dataset must contain "
                      << m.data_subdir << "/<run>/\n";
            return 2;
        }
        if (is_within(output, input) || is_within(input, output)) {
            std::cerr << m.name << ": output must be outside the dataset (and not contain it)\n";
            return 2;
        }

        const fs::path blackbox = find_blackbox(blackbox_arg, executable_dir(argv[0]), m);
        if (!has_all(blackbox, m)) {
            std::cerr << m.name << ": " << blackbox << " must contain " << m.script;
            for (const auto& t : m.tools) std::cerr << ", " << t;
            std::cerr << "\n(use --blackbox DIR or set WARTPC_BLACKBOX)\n";
            return 2;
        }

        fs::path setup;
        if (!no_setup) {
            if (!setup_arg.empty()) setup = fs::absolute(setup_arg);
            else if (const char* env = std::getenv("BLACKBOX_SETUP")) setup = fs::absolute(env);
            else if ((std::getenv("MODULESHOME") || std::getenv("LMOD_CMD")) &&
                     fs::is_regular_file(blackbox / "setup_blackbox.sh"))
                setup = blackbox / "setup_blackbox.sh";
            if (!setup.empty() && !fs::is_regular_file(setup)) {
                std::cerr << m.name << ": setup script " << setup << " not found\n";
                return 2;
            }
        }

        // 1. Mirror the dataset into the output folder.
        const std::vector<std::string> runs = run_dirs(src_runs);
        if (runs.empty()) { std::cerr << m.name << ": no run folders in " << src_runs << "\n"; return 2; }
        for (const auto& r : runs) mirror_run(src_runs / r, output / m.data_subdir / r, m);
        // charge_run.sh loops over optical/*/, so it needs those folder names.
        if (m.name == "charge") {
            std::vector<std::string> loop = run_dirs(input / "optical");
            if (loop.empty()) loop = runs;
            for (const auto& r : loop) fs::create_directories(output / "optical" / r);
        }

        // 2. The scripts call ./tpx3dump and python3 <script>.py from their cwd,
        //    so give them a private cwd holding links to the Blackbox tools.
        const fs::path tools = output / ".blackbox";
        fs::create_directories(tools);
        for (const auto& t : m.tools) {
            const fs::path link = tools / t;
            if (fs::is_symlink(fs::symlink_status(link)) || fs::exists(link)) fs::remove(link);
            fs::create_symlink(fs::canonical(blackbox / t), link);
        }

        // 3. Run the script, streaming output to the terminal and a log file.
        fs::create_directories(output / "logs");
        const std::string stamp = timestamp("%Y%m%d-%H%M%S");
        const fs::path log_path = output / "logs" / (m.name + "_" + stamp + ".log");
        std::ofstream log(log_path);
        std::ostringstream header;
        header << "# " << m.name << " started " << timestamp("%Y-%m-%d %H:%M:%S") << "\n"
               << "# input:    " << input.string() << "\n"
               << "# output:   " << output.string() << "\n"
               << "# blackbox: " << blackbox.string() << "\n"
               << "# script:   " << (blackbox / m.script).string() << "\n"
               << "# setup:    " << (setup.empty() ? "(none)" : setup.string()) << "\n"
               << "# runs:     " << runs.size() << "\n";
        std::cout << header.str() << std::flush;
        log << header.str() << std::flush;

        const std::string inner =
            "cd \"$1\" || exit 1; if [ -n \"$2\" ]; then source \"$2\"; fi; exec bash \"$3\" \"$4\"";
        const std::string cmd = std::string("bash ") + (setup.empty() ? "" : "-l ") + "-c " +
            shell_quote(inner) + " wartpc " + shell_quote(tools.string()) + " " +
            shell_quote(setup.string()) + " " + shell_quote((blackbox / m.script).string()) + " " +
            shell_quote(output.string()) + " 2>&1";

        const auto t0 = std::chrono::steady_clock::now();
        FILE* pipe = popen(cmd.c_str(), "r");
        if (!pipe) { std::cerr << m.name << ": failed to start bash\n"; return 1; }
        char buf[4096];
        while (std::fgets(buf, sizeof buf, pipe)) {
            std::cout << buf << std::flush;
            log << buf << std::flush;
        }
        const int status = pclose(pipe);
        const int script_rc = WIFEXITED(status) ? WEXITSTATUS(status) : -1;
        const long secs = std::chrono::duration_cast<std::chrono::seconds>(
            std::chrono::steady_clock::now() - t0).count();

        // 4. The scripts' exit codes are unreliable, so check each run's output.
        std::vector<std::string> failed;
        for (const auto& r : runs) {
            const fs::path marker = output / m.data_subdir / r / m.done_marker;
            if (!fs::is_regular_file(marker) || fs::file_size(marker) == 0) failed.push_back(r);
        }
        std::ostringstream summary;
        summary << "\n# finished in " << secs << " s (script exit code " << script_rc << ")\n"
                << "# completed " << runs.size() - failed.size() << "/" << runs.size() << " runs\n";
        for (const auto& r : failed)
            summary << "# FAILED " << r << ": no " << m.data_subdir << "/" << r << "/" << m.done_marker << "\n";
        summary << "# results: " << (output / m.data_subdir / "results").string() << "\n"
                << "# log:     " << log_path.string() << "\n";
        std::cout << summary.str();
        log << summary.str();

        std::ofstream(output / (m.name + "_status.txt")) << summary.str().substr(1);
        return failed.empty() ? 0 : 1;
    } catch (const fs::filesystem_error& e) {
        std::cerr << m.name << ": " << e.what() << "\n";
        return 1;
    }
}
