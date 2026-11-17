# SPDX-License-Identifier: MIT
# Run with Diamond pnmainc, or source from its Tcl Console. No device programming.
set root [file normalize [file dirname [info script]]]
set build [file join $root build]
if {[file exists [file join $build f1_ulx3s.ldf]]} {error "Project exists: prepare a fresh bundle instead of overwriting results"}
file mkdir $build
cd $build
prj_project new -name f1_ulx3s -impl impl -dev LFE5U-85F-6BG381C -synthesis synplify -lpf [file join $root carrier.lpf]
foreach source [lsort [glob [file join $root src *.sv]]] {
    prj_src add $source
}
prj_src add [file join $root synthesis.sdc]
prj_impl option top revc_ulx3s_diamond_top
prj_project save
prj_run Synthesis -impl impl
prj_run Translate -impl impl
prj_project save
prj_project close
puts "PREPARED: inspect translated clock names, CDC, IO and constraints before route.tcl. Not timing closure."
