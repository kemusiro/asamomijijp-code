package jp.or.rim.kt.kemusiro.sound;

/**
 * イベントを表すクラス。
 *
 * @version $Revision: 1.1.1.1 $
 * @author 宮田賢一(kemusiro@kt.rim.or.jp)
 */
public abstract class MusicEvent implements Comparable {
    protected int tick;
    protected int channel;

    public int compareTo(Object o) {
	if (o instanceof MusicEvent) {
	    MusicEvent e = (MusicEvent)o;
	    if (this.tick < e.tick) {
		return -1;
	    }
	    else if (this.tick > e.tick) {
		return 1;
	    }
	    else {
		return 0;
	    }
	}
	else {
	    throw new ClassCastException();
	}
    }

    /**
     * ティック数を得る。
     *
     * @return ティック数
     */
    public int getTick() {
	return tick;
    }

    /**
     * チャンネル番号を得る。
     *
     * @return チャネル番号
     */
    public int getChannel() {
	return channel;
    }
}
