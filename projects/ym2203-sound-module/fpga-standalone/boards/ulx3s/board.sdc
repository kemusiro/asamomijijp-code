# Physical clocks. nextpnr propagates the PLL ratio from ref12 to clocks.clk.
# No false paths or asynchronous clock-group cuts are requested.
create_clock -name usb_reference -period 83.333333333333 [get_ports ref12]
create_clock -name audio -period 20.345052083333 [get_ports audio49]
# 48MHz physical PLL output; 50MHz setup target reserves 0.833ns per cycle.
create_clock -name control_setup_budget -period 20.0 [get_nets clk]
