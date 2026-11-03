#!/usr/bin/env python3
"""デスクトップユーザーの2画面autostartを設定する。計算サービスは変更しない。"""

from datetime import datetime
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

START = "cluster-dual-kiosk:start"
END = "cluster-dual-kiosk:end"


def exec_quote(value):
    # Exec引数の引用後、Desktop Entryのstring値用にもう一度\をescapeする。
    value = str(value)
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("autostartの引数に改行・制御文字は使えません")
    value = value.replace("%", "%%")
    for character in ("\\", '"', "`", "$"):
        value = value.replace(character, "\\" + character)
    return '"' + value.replace("\\", "\\\\") + '"'


def backup_file(config, source, stem):
    if source.exists():
        backups = config / "cluster-dual-kiosk-backups"
        backups.mkdir(parents=True, exist_ok=True)
        destination = backups / (stem + "-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + source.suffix)
        shutil.copy2(source, destination)
        return destination
    return None


def configure_labwc(config, vehicle_output, pico_output, vehicle_identifier, pico_identifier):
    destination = config / "labwc/rc.xml"
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    if destination.exists():
        tree = ET.parse(destination, parser=parser)
        root = tree.getroot()
    else:
        root = ET.Element("labwc_config")
        tree = ET.ElementTree(root)
    namespace = root.tag.split("}")[0][1:] if root.tag.startswith("{") else ""
    if namespace:
        ET.register_namespace("", namespace)

    def tag(name):
        return "{" + namespace + "}" + name if namespace else name

    rules = root.find(tag("windowRules"))
    if rules is None:
        rules = ET.SubElement(root, tag("windowRules"))
    # 不完全な管理マーカーでは以降の無関係なルールを削除しない。
    managed, removals = False, []
    for rule in rules:
        marker = rule.text if rule.tag is ET.Comment else None
        if marker == START:
            if managed:
                raise ValueError("labwcの管理コメントが重複しています。rc.xmlを確認してください")
            managed = True
        elif marker == END and not managed:
            raise ValueError("labwcの管理コメントの対応が不正です。rc.xmlを確認してください")
        if managed or rule.get("identifier") in ("cluster-traffic-kiosk", "cluster-pico-kiosk"):
            removals.append(rule)
        if marker == END:
            managed = False
    if managed:
        raise ValueError("labwcの管理コメントが閉じていません。rc.xmlを確認してください")
    for rule in removals:
        rules.remove(rule)
    rules.append(ET.Comment(START))
    # labwcが照合するChromium Xwayland appの識別子はURLのホスト名。
    for identifier, output in ((vehicle_identifier, vehicle_output), (pico_identifier, pico_output)):
        rule = ET.SubElement(rules, tag("windowRule"), {"identifier": identifier, "serverDecoration": "no"})
        ET.SubElement(rule, tag("action"), {"name": "MoveToOutput", "output": output})
        ET.SubElement(rule, tag("action"), {"name": "ToggleFullscreen"})
    rules.append(ET.Comment(END))
    destination.parent.mkdir(parents=True, exist_ok=True)
    backup_file(config, destination, "labwc")
    temporary = destination.with_suffix(".xml.tmp")
    tree.write(temporary, encoding="utf-8", xml_declaration=True)
    temporary.replace(destination)


def main():
    if os.geteuid() == 0:
        raise SystemExit("sudoを使わず、Pi 5のデスクトップユーザーで実行してください。")
    launcher = Path(__file__).with_name("start-dual-display-kiosk.py").resolve()
    spec = importlib.util.spec_from_file_location("dual_kiosk", launcher)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    args = module.parse_args()
    arguments = [sys.executable, str(launcher), "--vehicle-url", args.vehicle_url, "--pico-url", args.pico_url,
                 "--vehicle-position=" + args.vehicle_position, "--pico-position=" + args.pico_position,
                 "--window-size", args.window_size, "--browser", args.browser,
                 "--profile-dir", str(args.profile_dir.resolve())]
    if args.no_http_recovery:
        arguments.append("--no-http-recovery")
    if args.vehicle_output:
        if not shutil.which("labwc"):
            raise SystemExit("labwcがありません。出力名指定はlabwc専用です。")
        arguments.extend(["--vehicle-output", args.vehicle_output, "--pico-output", args.pico_output])
    desktop = ("[Desktop Entry]\nType=Application\nName=Cluster Dual Display\nExec=" +
               " ".join(exec_quote(value) for value in arguments) +
               "\nTerminal=false\nX-GNOME-Autostart-enabled=true\n")
    if args.dry_run:
        print(desktop)
        return
    config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    if args.vehicle_output:
        if not os.environ.get("LABWC_PID", "").isdigit():
            raise SystemExit("LABWC_PIDがありません。Pi 5のlabwcデスクトップ端末で実行してください。設定は変更していません。")
        destination = config / "labwc/rc.xml"
        original = destination.read_bytes() if destination.exists() else None
        try:
            configure_labwc(config, args.vehicle_output, args.pico_output,
                            urlsplit(args.vehicle_url).hostname, urlsplit(args.pico_url).hostname)
        except (ET.ParseError, ValueError) as exc:
            raise SystemExit("labwc設定を更新できません。元のrc.xmlを確認してください: " + str(exc))
        try:
            subprocess.run(["labwc", "--reconfigure"], check=True, capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            if original is None:
                destination.unlink()
            else:
                destination.write_bytes(original)
            raise SystemExit("labwc再読込に失敗したため設定ファイルを戻しました。対象セッションとLABWC_PIDを確認してください: " + str(exc))
    autostart = config / "autostart"
    autostart.mkdir(parents=True, exist_ok=True)
    destination = autostart / "cluster-dual-kiosk.desktop"
    legacy = autostart / "pico-raytracing-kiosk.desktop"
    for source, stem in ((destination, "cluster-dual-kiosk"), (legacy, "pico-raytracing-kiosk")):
        saved = backup_file(config, source, stem)
        if saved:
            print("既存設定を保存しました: " + str(saved))
    temporary = destination.with_suffix(".desktop.tmp")
    temporary.write_text(desktop, encoding="utf-8")
    temporary.replace(destination)
    if legacy.exists():
        legacy.unlink()
    print("設定完了: " + str(destination))
    print("次回デスクトップログインから2画面表示します。現在のブラウザと計算サービスは継続します。")


if __name__ == "__main__":
    main()
