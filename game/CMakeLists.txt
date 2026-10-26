# fifa08 - ReXGlue Recompiled Project
#
# SDK boilerplate lives in generated/rexglue.cmake.

cmake_minimum_required(VERSION 3.25)
project(fifa08 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(generated/rexglue.cmake)

# Build the game from XenonRecomp's output (xenon/ppc, see xenon/README.md) instead
# of ReXGlue's generated code. The ReXGlue runtime is used either way.
option(FIFA08_USE_XENONRECOMP "Use XenonRecomp's recompiled code" OFF)
if(FIFA08_USE_XENONRECOMP)
    set(FIFA08_XENON_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../xenon")
    file(GLOB FIFA08_XENON_SOURCES "${FIFA08_XENON_DIR}/ppc/ppc_recomp.*.cpp")
    if(NOT FIFA08_XENON_SOURCES)
        message(FATAL_ERROR "No XenonRecomp output in ${FIFA08_XENON_DIR}/ppc; run XenonRecomp first")
    endif()
    set(REXGLUE_ENTRYPOINT_GENERATED_SOURCES
        ${FIFA08_XENON_SOURCES}
        "${FIFA08_XENON_DIR}/ppc/ppc_func_mapping.cpp"
        "${FIFA08_XENON_DIR}/xenon_init.cpp")
endif()

# Cross builds (Android) import an ARM64 rexglue that can't run on the build
# machine; run codegen with the host SDK's rexglue instead (its output is
# platform independent).
if(ANDROID)
    set(REXGLUE_HOST_CODEGEN
        "${CMAKE_CURRENT_SOURCE_DIR}/../third_party/rexglue-sdk/out/install/win-amd64/bin/rexglue.exe"
        CACHE FILEPATH "rexglue executable that runs on the build machine")
    set_target_properties(rex::rexglue PROPERTIES
        IMPORTED_LOCATION "${REXGLUE_HOST_CODEGEN}"
        IMPORTED_LOCATION_RELEASE "${REXGLUE_HOST_CODEGEN}")
endif()

# Sources
set(FIFA08_SOURCES
    src/main.cpp
)

if(WIN32)
    add_executable(fifa08 WIN32 ${FIFA08_SOURCES})
elseif(ANDROID)
    # SDL3's Android activity loads the game from libmain.so.
    add_library(fifa08 SHARED ${FIFA08_SOURCES})
    set_target_properties(fifa08 PROPERTIES OUTPUT_NAME main)
else()
    add_executable(fifa08 ${FIFA08_SOURCES})
endif()

rexglue_setup_target(fifa08 GPU_PLUGINS xenos)

if(FIFA08_USE_XENONRECOMP)
    target_include_directories(fifa08_recomp PRIVATE "${FIFA08_XENON_DIR}")
    set_source_files_properties(${REXGLUE_ENTRYPOINT_GENERATED_SOURCES}
        PROPERTIES COMPILE_OPTIONS "${REXGLUE_RECOMP_OPTIONS}")
endif()

# FSR / CAS (SDK built with REXGLUE_ENABLE_FIDELITYFX=ON): rexruntime needs
# amd_fidelityfx_dx12.dll at run time; put it next to fifa08.exe.
if(WIN32 AND TARGET rex::amd_fidelityfx_dx12)
    add_custom_command(TARGET fifa08 POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
            $<TARGET_FILE:rex::amd_fidelityfx_dx12> $<TARGET_FILE_DIR:fifa08>
        VERBATIM)
endif()
