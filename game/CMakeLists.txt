# fifa08 - ReXGlue Recompiled Project
#
# SDK boilerplate lives in generated/rexglue.cmake.

cmake_minimum_required(VERSION 3.25)
project(fifa08 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(generated/rexglue.cmake)

# Sources
set(FIFA08_SOURCES
    src/main.cpp
)

if(WIN32)
    add_executable(fifa08 WIN32 ${FIFA08_SOURCES})
else()
    add_executable(fifa08 ${FIFA08_SOURCES})
endif()

rexglue_setup_target(fifa08 GPU_PLUGINS xenos)

# FSR / CAS (SDK built with REXGLUE_ENABLE_FIDELITYFX=ON): rexruntime needs
# amd_fidelityfx_dx12.dll at run time; put it next to fifa08.exe.
if(WIN32 AND TARGET rex::amd_fidelityfx_dx12)
    add_custom_command(TARGET fifa08 POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
            $<TARGET_FILE:rex::amd_fidelityfx_dx12> $<TARGET_FILE_DIR:fifa08>
        VERBATIM)
endif()
