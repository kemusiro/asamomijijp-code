# USB_C_HRO_M12_20201208

This footprint adapts the KiCad community footprint
`Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12` as shipped with KiCad 10.0.5.
The inherited body/courtyard graphics are a conservative assembly guide.

Source: https://gitlab.com/kicad/libraries/kicad-footprints/-/blob/master/Connector_USB.pretty/USB_C_Receptacle_HRO_TYPE-C-31-M-12.kicad_mod

The modified library footprint is distributed under the KiCad Libraries License,
CC-BY-SA 4.0 with the electronic-design exception. See `LICENSE.md`.
This attribution does not relicense the rest of the MIT project.

Changes (2026-11-18): HRO 2020-12-08 recommended land positions and dimensions,
datum at positioning holes, 5.79 mm PCB edge datum, shell slots and NPTH update,
oval outer GND lands, rounded remaining lands, clipped silkscreen,
and removal of the unverified legacy STEP reference.

Manufacturer dimensions were checked against the HRO drawing linked by
LCSC product C165948. The drawing is referenced, not redistributed here.
https://datasheet.lcsc.com/datasheet/pdf/9e56b777c022540fcce7c7f67825f55e.pdf?productCode=C165948

The manufacturer drawing specifies land envelopes; this footprint uses oval GND
lands and 25-percent rounded corners elsewhere to retain the existing 0.25 mm
hole clearance. It is not a literal rectangular-copper reproduction of the drawing.
Physical solderability and connector fit have not been tested.
