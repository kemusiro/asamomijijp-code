package jp.or.rim.kt.kemusiro.sound;

/**
 * 消音イベントを表すクラス。
 *
 * @version $Revision: 1.2 $
 * @author 宮田賢一(kemusiro@kt.rim.or.jp)
 */
public class NoteOff extends MusicEvent {
    private int number;		// 0 - 127
    private int velocity;	// 0 - 127 (0 means note-off)

    public NoteOff(int newTick, int newChannel, int newNumber, int newVelocity) {
	tick = newTick;
	channel = newChannel;
	number = newNumber;
	velocity = newVelocity;
    }

    public String toString() {
	return "Note OFF " + Integer.toString(number);
    }
}
