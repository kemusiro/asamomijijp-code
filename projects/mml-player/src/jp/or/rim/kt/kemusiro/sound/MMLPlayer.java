package jp.or.rim.kt.kemusiro.sound;

import java.io.IOException;
import javax.sound.sampled.LineListener;

/**
 * MMLを演奏する。
 *
 * @version $Revision: 1.7 $
 * @author 宮田賢一(kemusiro@kt.rim.or.jp)
 */
public class MMLPlayer implements Runnable {
    private MessagePrinter printer;
    private LineListener listener;
    private Thread thread;
    private String[] mmls;

    public MMLPlayer() {
	super();
	this.listener = null;
    }

    public MMLPlayer(LineListener listener) {
	super();
	this.listener = listener;
    }

    private static void usage() {
	System.out.println("java MMLPlayer MML1 [MML2 [MML3]]");
	System.exit(1);
    }

    public void setPrinter(MessagePrinter p) {
	printer = p;
    }

    public MessagePrinter getPrinter() {
	return printer;
    }

    /**
     * MML文字列を解析して再生する。
     * 演奏状態を監視し、演奏終了時にlockオブジェクトに対して
     * notify()が発行される。
     *
     * @param mmls MML文字列
     * @exception MMLException 不正なMML文字列か否か
     * @see SoundPlayer
     */
    public void play(String[] mmls) throws MMLException {
	int tickPerBeat = 240;
	int samplingRate = 22100;
	int bitDepth = 8;
	MusicScore score = new MusicScore(tickPerBeat, mmls.length);
	MMLCompiler compiler = new MMLCompiler(tickPerBeat, mmls.length);
	WaveInputStream in = new WaveInputStream(score, samplingRate, bitDepth);

	compiler.compile(score, mmls);
	StreamingSoundPlayer player =
	    new StreamingSoundPlayer(samplingRate, bitDepth, listener);
	byte[] buffer = new byte[samplingRate * player.getFrameSize() / 2];
	player.start();
	try {
	    int length = 0;
	    while (thread != null && length >= 0) {
		length = in.read(buffer, 0, buffer.length);
		if (length >= 0) {
		    player.write(buffer, 0, length);
		}
	    }
	    player.drain();
	    player.stop();
	    player.close();
	    player = null;
	}
	catch (IOException e) {
	    e.printStackTrace();
	    System.exit(1);
	}
    }

    public void start() {
	thread = new Thread(this);
	thread.setName("MMLPlayer");
	thread.start();
    }

    public void stop() {
	thread = null;
    }

    public void run() {
	try {
	    play(mmls);
	}
	catch (MMLException e) {
	    getPrinter().send(e.getMessage());
	}
	thread = null;
    }

    public void setMML(String[] mmls) {
	this.mmls = mmls;
    }

    /**
     * 引数で与えられたMML文字列を演奏する。
     *
     * @param args コマンドライン引数
     */
    public static void main(String[] args) {
	if (args.length == 0) {
	    usage();
	}
	if (args[0].equals("-f")) {
	    FMGeneralInstrument.readParameter(args[1]);
	    String[] new_args = new String[args.length - 2];
	    for (int i = 2; i < args.length; i++) {
		new_args[i - 2] = args[i];
	    }
	    args = new_args;
	}
	else {
	    FMGeneralInstrument.readParameter("fmparameters.txt");
	}
	MMLPlayer p = new MMLPlayer();
	p.setPrinter(new ConsolePrinter());
	p.setMML(args);
	p.start();
	try {
	    while (p.thread != null) {
		p.thread.sleep(500);
	    }
	}
	catch (InterruptedException e) {
	    System.out.println(e);
	}
	System.exit(0);
    }
}
