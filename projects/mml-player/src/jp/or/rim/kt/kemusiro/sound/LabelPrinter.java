package jp.or.rim.kt.kemusiro.sound;

import java.util.Vector;
import javax.swing.*;

/**
 * ラベルにテキストメッセージを送信する。
 *
 * @version $Revision: 1.1 $
 * @author 宮田賢一(kemusiro@kt.rim.or.jp)
 */
public class LabelPrinter implements MessagePrinter, Runnable {
    private Vector messages = new Vector();
    private JLabel label;

    public LabelPrinter(JLabel label) {
	this.label = label;
	Thread t = new Thread(this);
	t.setName("LabelPrinter");
	t.start();
    }

    public synchronized void send(String message) {
	messages.add(message);
	notify();
    }

    public synchronized void run() {
	try {
	    while (true) {
		wait();
		label.setText((String)messages.lastElement());
		messages.removeAllElements();
	    }
	}
	catch (InterruptedException e) {
	}
    }
}
