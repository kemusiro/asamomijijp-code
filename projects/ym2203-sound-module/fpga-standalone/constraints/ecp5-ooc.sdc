# Independent input clocks; no asserted phase relationship and no false-path waiver.
create_clock -name control -period 20.833333333333 [get_ports clk]
create_clock -name audio -period 20.345052083333 [get_ports audio_clk]
