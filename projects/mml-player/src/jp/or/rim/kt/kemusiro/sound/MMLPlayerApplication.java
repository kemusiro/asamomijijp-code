package jp.or.rim.kt.kemusiro.sound;

import javax.swing.*;
import java.awt.event.*;
import java.awt.*;

/**
 * MMLを演奏する。
 *
 * @version $Revision$
 * @author 宮田賢一(kemusiro@kt.rim.or.jp)
 */
public class MMLPlayerApplication extends JFrame {
    Container container;
    JDesktopPane desktop;

    public MMLPlayerApplication() {
	super("MML Player");

	container = this.getContentPane();
	desktop = new JDesktopPane();
	container.add(desktop);
	setSize(400, 300);
	show();
    }

    public static void main(String[] args) {
	MMLPlayerApplication frame = new MMLPlayerApplication();
    }
}
