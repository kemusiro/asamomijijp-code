package jp.or.rim.kt.kemusiro.sound;

/**
 * テンポを変えるイベントを表すクラス。
 *
 * @version $Revision: 1.2 $
 * @author 宮田賢一(kemusiro@kt.rim.or.jp)
 */
public class ChangeTempo extends MusicEvent {
    private int tempo;

    public ChangeTempo(int newTick, int newChannel, int newTempo) {
	tick = newTick;
	channel = newChannel;
	tempo = newTempo;
    }

    public int getTempo() {
	return tempo;
    }

    public String toString() {
	return "Change Tempo " + Integer.toString(tempo);
    }
}
