cmake_minimum_required(VERSION 3.14)
project(libmsxca VERSION 1.0.0 LANGUAGES C)

# libmsxca: cross-platform decompressor for MS-XCA "LZXNATIVE" (magic 0FF512EE)
# Xbox 360 xcompress blobs. Wraps libmspack's LZX ("lzxd") decoder with
# chunk-framing support.
#
# Produces a shared library:
#   Linux   -> libmsxca.so
#   macOS   -> libmsxca.dylib
#   Windows -> msxca.dll

set(MSXCA_SOURCES
    src/msxca.c
    src/lzxd.c
)

add_library(msxca SHARED ${MSXCA_SOURCES})

target_include_directories(msxca
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/src>
        $<INSTALL_INTERFACE:include>
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src
)

if(MSVC)
    target_compile_options(msxca PRIVATE /W3)
else()
    target_compile_options(msxca PRIVATE -O2 -Wall -Wno-unused-parameter)
    set_target_properties(msxca PROPERTIES
        POSITION_INDEPENDENT_CODE ON
        VERSION ${PROJECT_VERSION}
        SOVERSION 1)
endif()

# Only the two public symbols need exporting.
if(CMAKE_C_COMPILER_ID MATCHES "MSVC")
    set_target_properties(msxca PROPERTIES
        LINK_FLAGS "/EXPORT:msxca_decompress /EXPORT:msxca_free")
endif()

# --- Test program (optional) ---
option(BUILD_TEST "Build the test program" OFF)

if(BUILD_TEST)
    add_executable(test_msxca test/test_msxca.c)
    target_link_libraries(test_msxca PRIVATE msxca)
    target_include_directories(test_msxca PRIVATE src)

    enable_testing()
    add_test(NAME decompress COMMAND test_msxca)
endif()
