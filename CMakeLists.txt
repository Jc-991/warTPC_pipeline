cmake_minimum_required(VERSION 3.16)
project(warTPC_runner LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

include(GNUInstallDirs)
# Blackbox scripts and tools are installed here, next to bin/.
set(WARTPC_DATADIR "${CMAKE_INSTALL_DATADIR}/wartpc")

foreach(mode charge optical)
  add_executable(${mode} src/runner.cpp)
  target_compile_definitions(${mode} PRIVATE
    WARTPC_MODE="${mode}"
    WARTPC_SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}/blackbox"
    WARTPC_REL_DATADIR="${WARTPC_DATADIR}")
  target_compile_options(${mode} PRIVATE -Wall -Wextra)
  # GCC < 9 keeps std::filesystem in a separate library.
  if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU" AND CMAKE_CXX_COMPILER_VERSION VERSION_LESS 9)
    target_link_libraries(${mode} PRIVATE stdc++fs)
  endif()
endforeach()

# plot: launcher for plotting/plot.py
add_executable(plot src/plot.cpp)
target_compile_definitions(plot PRIVATE
  WARTPC_SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}"
  WARTPC_REL_DATADIR="${WARTPC_DATADIR}")
target_compile_options(plot PRIVATE -Wall -Wextra)
if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU" AND CMAKE_CXX_COMPILER_VERSION VERSION_LESS 9)
  target_link_libraries(plot PRIVATE stdc++fs)
endif()

install(TARGETS charge optical plot RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
install(PROGRAMS
  blackbox/charge_run.sh blackbox/optical_run.sh
  blackbox/optical-analysis.py blackbox/waveform-integrator.py blackbox/waveform-plotting.py
  DESTINATION ${WARTPC_DATADIR})
# tpx3dump is not in git (over GitHub's size limit); install it only if present.
install(PROGRAMS blackbox/tpx3dump DESTINATION ${WARTPC_DATADIR} OPTIONAL)
install(FILES blackbox/setup_blackbox.sh blackbox/spark_detection.py DESTINATION ${WARTPC_DATADIR})
install(PROGRAMS plotting/plot.py DESTINATION ${WARTPC_DATADIR}/plotting)
install(FILES reference/history.csv reference/figure26_reference.png
  DESTINATION ${WARTPC_DATADIR}/reference)
