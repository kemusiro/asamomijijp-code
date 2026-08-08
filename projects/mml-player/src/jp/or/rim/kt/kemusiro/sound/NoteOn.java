package jp.or.rim.kt.kemusiro.sound;

/**
 * 発音イベントを表すクラス。
 *
 * @version $Revision: 1.2 $
 * @author 宮田賢一(kemusiro@kt.rim.or.jp)
 */
public class NoteOn extends MusicEvent {
    private int number;		// 0 - 127
    private int velocity;	// 0 - 127 (0 means note-off)

    public NoteOn(int newTick, int newChannel, int newNumber, int newVelocity) {
	tick = newTick;
	channel = newChannel;
	number = newNumber;
	velocity = newVelocity;
    }

    public int getNumber() {
	return number;
    }

    public int getVelocity() {
	return velocity;
    }

    public String toString() {
	return "Note ON " + Integer.toString(number);
    }
}
