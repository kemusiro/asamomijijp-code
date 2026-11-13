"""Generate the proposed pin allocation, not a schematic or firmware."""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    physical = dict(zip(
        list(range(23)) + [26, 27, 28],
        [1, 2, 4, 5, 6, 7, 9, 10, 11, 12, 14, 15, 16, 17, 19, 20,
         21, 22, 24, 25, 26, 27, 29, 31, 32, 34],
    ))
    assignments = [(i, f"D{i}", "bidirectional", "SIO") for i in range(8)] + [
        (8, "A0", "output", "SIO"),
        (9, "A1", "output", "SIO"),
        (10, "I2S_DATA", "output", "PIO"),
        (11, "I2S_BCLK", "output", "PIO"),
        (12, "I2S_LRCK", "output", "PIO"),
        (13, "CS_N", "output", "SIO"),
        (14, "WR_N", "output", "SIO"),
        (15, "RD_N", "output", "SIO"),
        (16, "FM_SD", "input", "PIO"),
        (17, "FM_CLK", "input", "PIO"),
        (18, "FM_SH1", "input", "PIO"),
        (19, "FM_SH2", "input", "PIO"),
        (20, "HOST_SDA", "open-drain", "I2C0 slave"),
        (21, "HOST_SCL", "open-drain", "I2C0 slave"),
        (22, "ARM", "output", "SIO; external pulldown"),
        (26, "AUX_SDA", "open-drain", "I2C1 master"),
        (27, "AUX_SCL", "open-drain", "I2C1 master"),
        (28, "STATUS", "input", "SIO/IRQ"),
    ]
    gpio = [dict(gpio=g, pico_physical_pin=physical[g], signal=s,
                 direction=d, function=f) for g, s, d, f in assignments]
    expander = [
        ("GPA0", "RESET_RELEASE", "output", "0"),
        ("GPA1", "HP_ALLOW", "output", "0"),
        ("GPA2", "SPK_ALLOW", "output", "0"),
        ("GPA3", "DAC_ALLOW", "output", "0"),
        ("GPA4", "AUX0", "output", "0"),
        ("GPA5", "AUX1", "output", "0"),
        ("GPA6", "RESERVED_OUT0", "output", "0"),
        ("GPA7", "RESERVED_OUT1", "output", "0"),
        ("GPB0", "ID0", "input", "external pullup"),
        ("GPB1", "ID1", "input", "external pullup"),
        ("GPB2", "ID2", "input", "external pullup"),
        ("GPB3", "PRESENT_N", "input", "external pullup"),
        ("GPB4", "RESERVED_IN0", "input", "external pullup"),
        ("GPB5", "RESERVED_IN1", "input", "external pullup"),
        ("GPB6", "RESERVED_IN2", "input", "external pullup"),
        ("GPB7", "RESERVED_OUT2", "output", "0"),
    ]
    expander = [dict(pin=p, signal=s, direction=d, initialized_value=v)
                for p, s, d, v in expander]
    # Contact numbers are the electrical mating numbers, not a mirrored PCB view.
    contacts = [
        "+5V", "GND", "+5V", "GND", "+3V3_AUX", "GND",
        "D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7",
        "A0", "GND", "A1", "GND", "CS_N", "WR_N", "RD_N", "GND",
        "RESET_N", "ARM", "STATUS", "GND", "FM_SD", "FM_CLK",
        "FM_SH1", "FM_SH2", "GND", "AUX_SDA", "AUX_SCL", "GND",
        "ID0", "ID1", "ID2", "PRESENT_N", "AUX0", "AUX1",
        "AGND", "ANALOG_L", "AGND", "ANALOG_R", "AGND",
        "NC_ANALOG_RESERVED", "NC_RESERVED", "GND", "GND", "KEY_NC",
    ]
    gpio_by_name = {r["signal"]: r["gpio"] for r in gpio}
    exp_by_name = {r["signal"]: r["pin"] for r in expander}
    connector = []
    for pin, signal in enumerate(contacts, 1):
        if signal in ("GND", "AGND"):
            direction, voltage, origin = "reference", "0V", "common ground"
        elif signal in ("+5V", "+3V3_AUX"):
            direction, voltage, origin = "base-to-module", signal, "regulated supply"
        elif signal.startswith("NC_") or signal == "KEY_NC":
            direction, voltage, origin = "unconnected", "NC", "none"
        elif signal.startswith("ANALOG_"):
            direction, voltage, origin = "module-to-base", "AC line level", "module analog conditioner"
        elif signal == "RESET_N":
            direction, voltage, origin = "base-to-module", "3.3V", "ARM AND MCP23017.GPA0"
        elif signal in exp_by_name:
            direction = "module-to-base" if signal.startswith("ID") or signal == "PRESENT_N" else "base-to-module"
            voltage, origin = "3.3V", "MCP23017." + exp_by_name[signal]
        else:
            entry = next(r for r in gpio if r["signal"] == signal)
            direction = {"input": "module-to-base", "output": "base-to-module",
                         "bidirectional": "bidirectional", "open-drain": "open-drain"}[entry["direction"]]
            voltage, origin = "3.3V", "GP" + str(gpio_by_name[signal])
        connector.append(dict(pin=pin, row="odd" if pin % 2 else "even",
                              signal=signal, direction=direction, voltage=voltage, source=origin))

    profiles = [
        dict(chip="YM2203C", board_id=1, clock_hz=4000000,
             address_bits=1, readable=True, digital="YM3014 floating mono",
             required=["A0", "RD_N", "FM_SD", "FM_CLK", "FM_SH1", "RESET_N"],
             status="IRQ active-low", analog="SSG A/B/C mixed; duplicated L/R",
             memory="none", firmware="ym2203", limitation="physical timing and digital receiver unverified"),
        dict(chip="YM2608", board_id=2, clock_hz=8000000,
             address_bits=2, readable=True, digital="YM3016 linear stereo",
             required=["A0", "A1", "RD_N", "FM_SD", "FM_CLK", "FM_SH1", "FM_SH2", "RESET_N"],
             status="IRQ active-low", analog="SSG mono; duplicated L/R",
             memory="optional ADPCM memory; SRAM needs DRAM interface bridge",
             firmware="ym2608", limitation="memory bridge and serial timing unverified"),
        dict(chip="YM2610", board_id=3, clock_hz=8000000,
             address_bits=2, readable=True, digital="YM3016 linear stereo",
             required=["A0", "A1", "RD_N", "FM_SD", "FM_CLK", "FM_SH1", "FM_SH2", "RESET_N"],
             status="IRQ active-low", analog="SSG mono; duplicated L/R",
             memory="separate ADPCM-A/B memory interfaces and address latches",
             firmware="ym2610", limitation="initial 512KiB per bank is not full 16MiB support"),
        dict(chip="SN76489AN", board_id=4, clock_hz=3579545,
             address_bits=0, readable=False, digital="none",
             required=["STATUS"], status="READY active-high", analog="AUDIO OUT mono; duplicated L/R",
             memory="none", firmware="sn76489an",
             limitation="no reset pin; attenuation writes required; TI D0 is the byte MSB"),
        dict(chip="YMZ285", board_id=5, clock_hz=4096000,
             address_bits=0, readable=False, digital="none",
             required=["STATUS", "RESET_N"], status="PLAY active-low",
             analog="SO (SSG) and PO (PCM) conditioned and mixed; duplicated L/R",
             memory="internal 512Kbit OTP; programming not included", firmware="ymz285",
             limitation="normal CPU interface selects internal-ROM sequences/PCM; no documented arbitrary SSG register writes"),
        dict(chip="YMZ294", board_id=6, clock_hz=4000000,
             address_bits=1, readable=False, digital="none",
             required=["A0", "RESET_N"], status="none; connector STATUS undriven",
             analog="SO mono; duplicated L/R", memory="none", firmware="ymz294",
             limitation="4/6 selection fixed for 4MHz; TEST held high"),
    ]
    for p in profiles:
        p["required"] = [f"D{i}" for i in range(8)] + ["CS_N", "WR_N", "ARM"] + p["required"]
    data = dict(
        revision="A-proposal", date="2026-10-15", status="pin-budget-review-only",
        host="separate Pico 2 running MicroPython", controller="non-wireless Raspberry Pi Pico 2; C/C++",
        expander_model="MCP23017-E/SP at 3.3V; AUX I2C address 0x20",
        connector_type="2x25, 2.54mm keyed shrouded mating pair; final MPN/footprint pending",
        gpio=gpio, expander=expander, connector=connector, profiles=profiles,
        digital_connector_voltage=3.3, hot_swap=False,
        memory_realtime_on_module=True, mclk_from_pico=False,
        pio_budget={"fm_receiver_state_machines": 2, "i2s_state_machines": 1,
                    "planned_blocks": 2, "available_blocks": 3,
                    "dma_channels_planned": 6, "dma_channels_available": 16,
                    "note": "allocation budget only; no assembled PIO program or measured throughput"},
    )
    (ROOT / "design.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    for filename, rows in [("gpio.csv", gpio), ("connector.csv", connector), ("expander.csv", expander)]:
        with (ROOT / filename).open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    print("Generated design.json, gpio.csv, connector.csv, expander.csv")


if __name__ == "__main__":
    main()
