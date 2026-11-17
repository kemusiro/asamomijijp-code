# SPDX-License-Identifier: MIT
# Run only after the translated preferences and timing scope have been reviewed.
set root [file normalize [file dirname [info script]]]
cd [file join $root build]
prj_project open [file join $root build f1_ulx3s.ldf]
prj_run Map -impl impl
prj_run PAR -impl impl
prj_run PAR -impl impl -task PARTrace
prj_project save
prj_project close
puts "REPORTS ONLY: review setup/hold/recovery/removal and unconstrained paths; no Bitgen or programming."
