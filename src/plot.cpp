// `plot`: launcher for plotting/plot.py.
//
//   plot -i <result_dir> -o <plot_dir> [options]
//
// Loads the cluster environment (as `charge`/`optical` do), then runs
// plot.py with the remaining arguments. Options handled here:
//   --setup FILE   source FILE first (default: $BLACKBOX_SETUP, else the bundled
//                  setup_blackbox.sh when a module system is present)
//   --no-setup     source nothing
// $WARTPC_PYTHON selects the interpreter (default: python3).

#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <string>
#include <unistd.h>
#include <vector>

#if defined(__APPLE__)
#include <mach-o/dyld.h>
#endif

namespace fs = std::filesystem;

#ifndef WARTPC_SOURCE_DIR
#define WARTPC_SOURCE_DIR "."
#endif
#ifndef WARTPC_REL_DATADIR
#define WARTPC_REL_DATADIR "share/wartpc"
#endif

static fs::path executable_dir(const char* argv0) {
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

int main(int argc, char** argv) {
    // Installed layout first (share/wartpc/plotting/plot.py), then the source tree.
    const fs::path installed = executable_dir(argv[0]).parent_path() / WARTPC_REL_DATADIR;
    const fs::path source = WARTPC_SOURCE_DIR;
    fs::path root = fs::is_regular_file(installed / "plotting/plot.py") ? installed : source;
    const fs::path script = root / "plotting/plot.py";
    if (!fs::is_regular_file(script)) {
        std::cerr << "plot: cannot find plotting/plot.py (looked in " << installed << " and " << source << ")\n";
        return 2;
    }
    const fs::path bundled_setup = fs::is_regular_file(root / "setup_blackbox.sh")
                                       ? root / "setup_blackbox.sh" : root / "blackbox/setup_blackbox.sh";

    std::string setup;
    bool no_setup = false, setup_given = false;
    std::vector<std::string> pass;
    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        if (a == "--no-setup") no_setup = true;
        else if (a == "--setup") {
            if (i + 1 >= argc) { std::cerr << "plot: --setup needs a value\n"; return 2; }
            setup = fs::absolute(argv[++i]).string();
            setup_given = true;
        } else pass.push_back(a);
    }
    bool help = false;
    for (const auto& a : pass) help |= (a == "-h" || a == "--help");
    if (!no_setup && !setup_given && !help) {
        if (const char* env = std::getenv("BLACKBOX_SETUP")) setup = fs::absolute(env).string();
        else if ((std::getenv("MODULESHOME") || std::getenv("LMOD_CMD")) && fs::is_regular_file(bundled_setup))
            setup = bundled_setup.string();
    }
    if (no_setup) setup.clear();
    if (!setup.empty() && !fs::is_regular_file(setup)) {
        std::cerr << "plot: setup script " << setup << " not found\n";
        return 2;
    }
    const char* py_env = std::getenv("WARTPC_PYTHON");
    const std::string python = py_env ? py_env : "python3";

    // bash [-l] -c '...' plot <setup> <python> <script> args...
    const std::string inner =
        "s=\"$1\"; py=\"$2\"; shift 2; if [ -n \"$s\" ]; then source \"$s\" >&2; fi; exec \"$py\" \"$@\"";
    std::vector<std::string> args = {"bash"};
    if (!setup.empty()) args.push_back("-l");
    args.insert(args.end(), {"-c", inner, "plot", setup, python, script.string()});
    args.insert(args.end(), pass.begin(), pass.end());

    std::vector<char*> cargs;
    for (auto& s : args) cargs.push_back(s.data());
    cargs.push_back(nullptr);
    execvp("bash", cargs.data());
    std::perror("plot: failed to start bash");
    return 1;
}
