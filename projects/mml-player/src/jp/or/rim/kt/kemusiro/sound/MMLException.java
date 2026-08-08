package jp.or.rim.kt.kemusiro.sound;

/**
 * MMLの文法エラーを表すクラス。
 *
 * @version $Revision: 1.2 $
 * @author 宮田賢一(kemusiro@kt.rim.or.jp)
 */
public class MMLException extends Exception {
    public MMLException() {
	super();
    }

    public MMLException(String message) {
	super(message);
    }
}
