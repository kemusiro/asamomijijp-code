package jp.or.rim.kt.kemusiro.sound;

import java.io.FileReader;
import java.io.BufferedReader;
import java.io.IOException;
import java.util.Vector;
import jp.or.rim.kt.kemusiro.sound.tone.FMParameter;
import jp.or.rim.kt.kemusiro.sound.tone.FMAlgorithm;
import jp.or.rim.kt.kemusiro.sound.tone.FMAlgorithm0;
import jp.or.rim.kt.kemusiro.sound.tone.FMAlgorithm1;
import jp.or.rim.kt.kemusiro.sound.tone.FMAlgorithm2;
import jp.or.rim.kt.kemusiro.sound.tone.FMAlgorithm3;
import jp.or.rim.kt.kemusiro.sound.tone.FMAlgorithm4;
import jp.or.rim.kt.kemusiro.sound.tone.FMAlgorithm5;
import jp.or.rim.kt.kemusiro.sound.tone.FMAlgorithm6;
import jp.or.rim.kt.kemusiro.sound.tone.FMAlgorithm7;
import jp.or.rim.kt.kemusiro.sound.tone.Envelope;
import jp.or.rim.kt.kemusiro.sound.tone.DummyEnvelope;

/**
 * 汎用FM音源楽器。
 *
 * @version $Revision: 1.2 $
 * @author 宮田賢一(kemusiro@kt.rim.or.jp)
 */
public class FMGeneralInstrument extends Instrument {
    private static Vector parameters = new Vector();

    public FMGeneralInstrument(int number) {
	FMParameter p = findParameter(number);
	if (p == null) {
	    throw new RuntimeException("can't find tone number: " + number);
	}
	else {
	    switch (p.getAlgorithm()) {
	    case 0:
		wave = new FMAlgorithm0(p);
		break;
	    case 1:
		wave = new FMAlgorithm1(p);
		break;
	    case 2:
		wave = new FMAlgorithm2(p);
		break;
	    case 3:
		wave = new FMAlgorithm3(p);
		break;
	    case 4:
		wave = new FMAlgorithm4(p);
		break;
	    case 5:
		wave = new FMAlgorithm5(p);
		break;
	    case 6:
		wave = new FMAlgorithm6(p);
		break;
	    case 7:
		wave = new FMAlgorithm7(p);
		break;
	    default:
		throw new RuntimeException("invalid algorithm number");
	    }
	}
	envelope = new DummyEnvelope();
    }

    private static FMParameter findParameter(int number) {
	for (int i = 0; i < parameters.size(); i++) {
	    FMParameter p = (FMParameter)parameters.elementAt(i);
	    if (p.getToneNumber() == number) {
		return p;
	    }
	}
	return null;
    }

    public static void readParameter(String filename) {
	try {
	    BufferedReader in = new BufferedReader(new FileReader(filename));
	    String line;

	    for (line = in.readLine(); line != null; line = in.readLine()) {
		int toneNumber = Integer.parseInt(line);
		int opCount = 4;
		FMParameter p = new FMParameter(toneNumber, opCount);
		p.setAlgorithm(Integer.parseInt(in.readLine()));
		for (int op = 0; op < opCount; op++) {
		    p.setMultiplier(op, Double.parseDouble(in.readLine()));
		    p.setAttackRate(op, Double.parseDouble(in.readLine()));
		    p.setDecayRate(op, Double.parseDouble(in.readLine()));
		    p.setSustainRate(op, Double.parseDouble(in.readLine()));
		    p.setReleaseRate(op, Double.parseDouble(in.readLine()));
		    p.setSustainLevel(op, Double.parseDouble(in.readLine()));
		    p.setMaxLevel(op, Double.parseDouble(in.readLine()));
		}
		parameters.add(p);
	    }
	    in.close();
	}
	catch (IOException e) {
	    System.out.println(e.toString());
	    System.exit(1);
	}
    }

    public static void setParameter(int number, FMParameter newParameter) {
	FMParameter p = findParameter(number);
	if (p != null) {
	    parameters.remove(p);
	    parameters.add(newParameter);
	}
	else {
	    parameters.add(newParameter);
	}
    }

    public void setTimeStep(double newTimeStep) {
	super.setTimeStep(newTimeStep);
	((FMAlgorithm)wave).setTimeStep(newTimeStep);
    }

    public void press() {
	super.press();
	((FMAlgorithm)wave).press();
    }

    public void release() {
	super.release();
	((FMAlgorithm)wave).release();
    }

    public String getName() {
	return toString();
    }

    public String toString() {
	return "FM General";
    }
}
