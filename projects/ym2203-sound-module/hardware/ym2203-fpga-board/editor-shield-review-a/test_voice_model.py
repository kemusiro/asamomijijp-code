# SPDX-License-Identifier: MIT
import copy,json,unittest
import voice_model as M

class VoiceTests(unittest.TestCase):
    def test_json_roundtrip(self):
        v=M.default_voice();v['name']='音色 A';self.assertEqual(M.loads(M.dumps(v)),v)
    def test_invalid_import(self):
        v=M.default_voice()
        for field,bad in [('algorithm',8),('feedback',True),('preview_velocity',0),('clock_hz',0),('name','x'*25)]:
            w=copy.deepcopy(v);w[field]=bad
            with self.assertRaises(ValueError):M.validate(w)
        with self.assertRaises(ValueError):M.loads('{"format":1,"format":2}')
        with self.assertRaises(ValueError):M.loads(' '*4097)
        for index,field in enumerate(M.FIELDS):
            w=copy.deepcopy(v);w['operators'][0][field]=M.LIMITS[index]+1
            with self.assertRaises(ValueError):M.validate(w)
    def test_slot_map_and_reserved_bits(self):
        v=M.default_voice()
        for i,p in enumerate(v['operators']):p['tl']=i+10;p['ar']=31;p['ks']=3;p['dt']=7;p['mul']=15
        plan=M.register_plan(v,1);d=dict(plan)
        self.assertEqual([d[r] for r in (0x41,0x49,0x45,0x4d)],[10,11,12,13]);self.assertEqual(d[0x51],0xdf);self.assertEqual(d[0x31],0x7f)
        self.assertEqual(len(plan),30);self.assertEqual(plan[0],(0x28,1));self.assertFalse(any(r<0x30 for r,_ in plan[1:]));self.assertFalse(any(r>=0xb4 for r,_ in plan))
        for ch in (-1,3,True):
            with self.assertRaises(ValueError):M.register_plan(v,ch)
    def test_all_presets(self):
        m=bytearray(M.SIZE);v=M.default_voice()
        for slot in range(64):
            v['name']='slot '+str(slot);M.save(m,slot,v);self.assertEqual(M.active(m,slot)[1],v)
    def test_power_cut_at_every_byte(self):
        m=bytearray(M.SIZE);v=M.default_voice();M.save(m,5,v);v['name']='current';M.save(m,5,v);w=copy.deepcopy(v);w['name']='new value'
        for cut in range(257):
            mem=bytearray(m);self.assertFalse(M.save(mem,5,w,cut_after=cut));self.assertEqual(M.active(mem,5)[1],v)
        self.assertTrue(M.save(m,5,w));self.assertEqual(M.active(m,5)[1],w)
    def test_corruption_crc_identity(self):
        v=M.default_voice();data=M.encode(v,3,0)
        for index in range(256):
            corrupted=bytearray(data);corrupted[index]^=1
            with self.assertRaises(ValueError):M.decode(corrupted,3)
        with self.assertRaises(ValueError):M.decode(data,4)
    def test_generation_wrap(self):
        m=bytearray(M.SIZE);v=M.default_voice();m[:256]=M.encode(v,0,0xffffffff);v['name']='wrapped';M.save(m,0,v);self.assertEqual(M.active(m,0)[2],0)
    def test_pickup(self):
        p=M.Pickup(2000);self.assertIsNone(p.sample(50));self.assertIsNone(p.sample(1900));self.assertEqual(p.sample(2100),2100);self.assertEqual(p.sample(3000),3000)
        q=M.Pickup(2000);self.assertEqual(q.sample(1990),1990)
    def test_read_only_import_plan(self):
        v=M.loads(M.dumps(M.default_voice()));self.assertEqual(v,M.default_voice())
        m=bytearray(M.SIZE)
        with self.assertRaises(ValueError):M.active(m,0)
if __name__=='__main__':unittest.main()
