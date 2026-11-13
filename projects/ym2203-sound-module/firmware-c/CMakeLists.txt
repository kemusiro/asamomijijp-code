cmake_minimum_required(VERSION 3.17)
set(PICO_BOARD pico2 CACHE STRING "Approved board")
if(NOT DEFINED ENV{PICO_SDK_PATH})
  message(FATAL_ERROR "Set PICO_SDK_PATH to the pinned Pico SDK 2.2.0")
endif()
include($ENV{PICO_SDK_PATH}/external/pico_sdk_import.cmake)
project(ym2203_revc_c C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
pico_sdk_init()
if(NOT PICO_SDK_VERSION_STRING STREQUAL "2.2.0")
  message(FATAL_ERROR "This prototype is pinned to Pico SDK 2.2.0")
endif()
if(NOT PICO_BOARD STREQUAL "pico2")
  message(FATAL_ERROR "Use the approved Pico 2 (Arm) target")
endif()
find_package(Python3 REQUIRED COMPONENTS Interpreter)
set(REVC_SONG "" CACHE FILEPATH "Local-only WYM1 data;empty builds an original test scale")
add_custom_command(OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/song_data.c
  COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/embed_song.py
    --input "${REVC_SONG}" --output ${CMAKE_CURRENT_BINARY_DIR}/song_data.c
    --report ${CMAKE_CURRENT_BINARY_DIR}/song-data.json
  DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/tools/embed_song.py ${REVC_SONG}
  VERBATIM)
add_executable(revc_c src/main.c src/board.c src/audio.c src/audio_start.c src/audio_dma.c src/diagnostic.c src/wym1.c src/usb.c src/stream.c src/transport.c src/i2c.c src/midi.c
  ${CMAKE_CURRENT_BINARY_DIR}/song_data.c)
target_include_directories(revc_c PRIVATE src)
pico_generate_pio_header(revc_c ${CMAKE_CURRENT_SOURCE_DIR}/pio/fm_rx.pio)
pico_generate_pio_header(revc_c ${CMAKE_CURRENT_SOURCE_DIR}/pio/i2s_tx.pio)
target_compile_definitions(revc_c PRIVATE PICO_STACK_SIZE=4096 PICO_CORE1_STACK_SIZE=4096)
target_compile_options(revc_c PRIVATE -Wall -Wextra -Werror -Wno-unused-parameter
  "-ffile-prefix-map=${CMAKE_CURRENT_SOURCE_DIR}=firmware-c"
  "-ffile-prefix-map=${CMAKE_CURRENT_BINARY_DIR}=build"
  "-ffile-prefix-map=${PICO_SDK_PATH}=pico-sdk")
target_link_libraries(revc_c pico_stdlib pico_multicore pico_unique_id hardware_dma
  hardware_pio hardware_clocks hardware_watchdog pico_i2c_slave tinyusb_device tinyusb_board)
pico_enable_stdio_uart(revc_c 0)
pico_enable_stdio_usb(revc_c 0)
pico_set_program_name(revc_c "YM2203 Rev C local WYM1")
pico_set_program_version(revc_c "0.5.0-alpha.3")
pico_add_extra_outputs(revc_c)
