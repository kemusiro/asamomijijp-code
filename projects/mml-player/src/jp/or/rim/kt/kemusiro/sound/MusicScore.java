package jp.or.rim.kt.kemusiro.sound;

import java.io.OutputStream;
import java.util.Iterator;
import java.util.LinkedList;

/**
 * 楽譜を表すクラス。
 *
 * @version $Revision: 1.3 $
 * @author 宮田賢一(kemusiro@kt.rim.or.jp)
 */
public final class MusicScore {
    private int tickPerBeat;
    private int channelCount;
    private LinkedList eventList;
    private int defaultTempo = 100;

    /**
     * 楽譜を新規に作成する。
     *
     * @param newTickPerBeat 1拍当たりのカウント数
     * @param newChannels チャネル数
     */
    public MusicScore(int newTickPerBeat, int newChannelCount) {
	tickPerBeat = newTickPerBeat;
	channelCount = newChannelCount;
	eventList = new LinkedList();

	for (int ch = 0; ch < newChannelCount; ch++) {
	    add(new ChangeInstrument(0, ch, new SquareWaveInstrument()));
	    add(new ChangeTempo(0, ch, defaultTempo));
	}
    }

    public int getTickPerBeat() {
	return tickPerBeat;
    }

    public LinkedList getEventList() {
	return eventList;
    }

    public int getChannelCount() {
	return channelCount;
    }

    /**
     * イベントを追加する。新しいイベントはリスト上で昇順に並ぶことを
     * 保証する。
     *
     * @param event イベント
     */
    public void add(MusicEvent event) {
	for (int i = eventList.size() - 1; i >= 0; i--) {
	    MusicEvent e = (MusicEvent)eventList.get(i);

	    if (e.getTick() <= event.getTick()) {
		eventList.add(i + 1, event);
		return;
	    }
	}
	eventList.add(0, event);
    }

    public void dump(OutputStream output) {
	for (Iterator i = eventList.iterator(); i.hasNext(); ) {
	    MusicEvent e = (MusicEvent)i.next();
	    System.out.print("tick:" + e.getTick());
	    System.out.print(" ch:" + e.getChannel());
	    System.out.println(e.toString());
	}
    }

    public String toString() {
	return "MusicScore: Ticks/Beat=" + tickPerBeat + " channelCount:" + channelCount;
    }
}
