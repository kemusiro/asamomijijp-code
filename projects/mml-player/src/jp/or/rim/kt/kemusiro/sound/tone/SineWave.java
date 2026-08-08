package jp.or.rim.kt.kemusiro.sound.tone;

/**
 * sin波を表すクラス。
 *
 * @version $Revision: 1.1 $
 * @author 宮田賢一(kemusiro@kt.rim.or.jp)
 */
public class SineWave implements WaveGeneratable {
    private static double[] frequencyTable;

    // normal temperament
    static {
	double base = 440.0;	// A: #69
	frequencyTable = new double[128];

	for (int i = 0; i < 128; i++) {
	    frequencyTable[i] = base * Math.pow(2.0, ((double)(i - 69)) / 12.0);
	}
    }

    public SineWave() {
    }

    /**
     * 指定の時刻の値を得る。波形の振幅は1.0に正規化される。
     *
     * @param number 音番号(0-127)
     * @param time 時刻
     * @return 波形値
     */
    public double getValue(int number, double time) {
	return Math.sin(2.0 * Math.PI * frequencyTable[number] * time);
    }

    public String toString() {
	return "Sine Wave";
    }
			      
}
