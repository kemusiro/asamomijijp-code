package jp.or.rim.kt.kemusiro.sound.tone;

/**
 * FM音源のアルゴリズム。
 *
 * @version $Revision: 1.1 $
 * @author 宮田賢一(kemusiro@kt.rim.or.jp)
 */
public abstract class FMAlgorithm implements WaveGeneratable {
    private FMOperator[] operators;

    public FMAlgorithm(int operatorCount) {
	operators = new FMOperator[operatorCount];
	for (int i = 0; i < operatorCount; i++) {
	    operators[i] = new FMOperator();
	}
    }

    public FMOperator getOperator(int op) {
	return operators[op];
    }

    public void setInput(int op, WaveGeneratable in1, WaveGeneratable in2) {
	operators[op].setInput(in1,in2);
    }

    public void setMultiplier(int op, double multiplier) {
	operators[op].setMultiplier(multiplier);
    }

    public void setMask(int op, boolean mask) {
	operators[op].setMask(mask);
    }

    public void setEnvelope(int op, Envelope envelope) {
	operators[op].setEnvelope(envelope);
    }

    public void setTimeStep(double newTimeStep) {
	for (int i = 0; i < operators.length; i++) {
	    operators[i].setTimeStep(newTimeStep);
	}
    }

    public void press() {
	for (int i = 0; i < operators.length; i++) {
	    operators[i].press();
	}
    }

    public void release() {
	for (int i = 0; i < operators.length; i++) {
	    operators[i].release();
	}
    }

    public abstract double getValue(int number, double time);

    protected void setParameter(FMParameter p) {
	for (int op = 0; op < 4; op++) {
	    setMultiplier(op, p.getMultiplier(op));
	    setEnvelope(op, new ADSREnvelope(p.getAttackRate(op),
					     p.getDecayRate(op),
					     p.getSustainRate(op),
					     p.getReleaseRate(op),
					     p.getSustainLevel(op),
					     p.getMaxLevel(op)));
	}
    }
}
