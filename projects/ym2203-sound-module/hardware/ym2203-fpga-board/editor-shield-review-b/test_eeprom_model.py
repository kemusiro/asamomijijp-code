# SPDX-License-Identifier: MIT
import unittest
import eeprom_model as E
import voice_model as M

class EEPROMTests(unittest.TestCase):
    def test_page_boundaries(self):
        for start in range(256):
            pieces=list(E.chunks(start,bytes(range(255))))
            self.assertEqual(b''.join(b for _,b in pieces),bytes(range(255)))
            for a,b in pieces:
                self.assertLessEqual(len(b),16)
                self.assertEqual(a//64,(a+len(b)-1)//64)
        with self.assertRaises(ValueError):list(E.chunks(M.SIZE-1,b'xx'))
    def test_commit_last_and_distinct_pages(self):
        v=M.default_voice()
        for slot in range(64):
            for copy in (0,1):
                p=E.save_plan(v,slot,copy,1);base=(slot*2+copy)*256
                self.assertEqual(p[0],('write',base+255,b'\0'))
                self.assertEqual(p[-3][0],'verify_uncommitted')
                self.assertEqual(p[-2],('write',base+255,b'\xa5'))
                self.assertEqual(p[-1][0],'verify_committed')
                for kind,a,b in p:
                    if kind=='write':self.assertEqual(a//256,base//256)
    def test_page_loss_preserves_active_copy(self):
        old=M.default_voice();new=M.default_voice();new['name']='updated'
        m=bytearray(M.SIZE);m[:256]=M.encode(old,0,1)
        # A failed programming pulse may corrupt the whole target page, not just a byte.
        for pattern in (0,255,0x55,0xaa):
            for page in range(4):
                t=bytearray(m);t[256:512]=M.encode(new,0,2)
                t[256+page*64:320+page*64]=bytes([pattern])*64
                self.assertIn(M.active(t,0)[1],(old,new))
                self.assertEqual(t[:256],m[:256])
    def test_bounded_ack_poll(self):
        self.assertEqual(E.poll_result(0,False),'pending')
        self.assertEqual(E.poll_result(5,True),'ready')
        with self.assertRaises(TimeoutError):E.poll_result(10,False)
if __name__=='__main__':unittest.main()
