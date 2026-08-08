package jp.or.rim.kt.kemusiro.sound;

import java.util.Vector;

/**
 * コンソールにテキストメッセージを送信する。
 *
 * @version $Revision: 1.1 $
 * @author 宮田賢一(kemusiro@kt.rim.or.jp)
 */
public class ConsolePrinter implements MessagePrinter, Runnable {
    private Vector messages = new Vector();

    public ConsolePrinter() {
	Thread t = new Thread(this);
	t.setName("ConsolePrinter");
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
		for (int i = 0; i < messages.size(); i++) {
		    System.out.println((String)messages.get(i));
		}
		messages.removeAllElements();
	    }
	}
	catch (InterruptedException e) {
	}
    }
}
