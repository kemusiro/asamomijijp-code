"""元コース由来の地形・有限幅の断面・旧平面の互換性を検査。"""
import copy
import math
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'host'),str(ROOT/'pico')]
from course_scene import make_course,terrain_for_source
from vehicle_scene import load_snapshot,DEFAULT_SNAPSHOT,make_job,core

class TerrainTests(unittest.TestCase):
    def test_course_seed_and_obstacle_landmarks(self):
        course=make_course(2026,'obstacles-v1');heights=dict(course)
        self.assertEqual([heights[x] for x in (24,30,33,48,51,57)],[0,4.5,4.5,-6,-6,0])
        self.assertEqual(course,make_course(2026,'obstacles-v1'))
        self.assertNotEqual(make_course(2026,'rolling-v1'),make_course(2027,'rolling-v1'))
        terrain=terrain_for_source({'courseSeed':2026,'courseProfile':'obstacles-v1'})
        self.assertEqual(terrain['sourceRange'],[9,66]);self.assertLessEqual(len(terrain['points']),24)
        self.assertEqual([p for p in terrain['points'] if abs(p[0])<=2.4],[[-2.4,-1],[2.4,-1]])
        self.assertAlmostEqual(min(p[1] for p in terrain['points']),-4.15)
        for seed in (-1,True,2147483648):
            with self.assertRaises(ValueError):make_course(seed,'rolling-v1')

    def test_tuned_course_and_renderable_diorama(self):
        course=make_course(2026,'obstacles-55-7p5-v1');heights=dict(course)
        self.assertAlmostEqual(math.degrees(math.atan((heights[27]-heights[24])/3)),55)
        self.assertEqual([heights[x] for x in (42,48,51,57)],[0,-7.5,-7.5,0])
        terrain=terrain_for_source({'courseSeed':2026,'courseProfile':'obstacles-55-7p5-v1'})
        self.assertAlmostEqual(min(p[1] for p in terrain['points']),-4.6)
        self.assertEqual(terrain['courseProfile'],'obstacles-55-7p5-v1')
        job=make_job(load_snapshot(DEFAULT_SNAPSHOT),'smooth',True);job['terrain']=terrain
        core.validate_job(job)
        self.assertEqual(len(core.compute_tile(job,0,16,16,16)),16*16*3)

    def test_finite_terrain_top_cutaway_and_outside(self):
        snapshot=load_snapshot(DEFAULT_SNAPSHOT);job=make_job(snapshot,'recovery',terrain=True)
        job['terrain']['points']=[[-4,-1],[0,-1],[4,-4]]
        core.validate_job(job);core._prepare(job['vehicle'],job['terrain'])
        top=core._nearest_hit(3,2,1.4,0,-1,0)
        self.assertEqual(top[1],0);self.assertAlmostEqual(top[0],5.25);self.assertAlmostEqual(top[2],.6);self.assertAlmostEqual(top[3],.8)
        side=core._nearest_hit(3,-4,-5,0,0,1)
        self.assertEqual(side[1],21);self.assertAlmostEqual(side[0],3.35);self.assertEqual(side[4],-1)
        self.assertEqual(core._nearest_hit(20,3,-5,0,1,0)[1],-1)

    def test_terrain_changes_do_not_reuse_previous_geometry_or_change_flat_job(self):
        snapshot=load_snapshot(DEFAULT_SNAPSHOT);flat=make_job(snapshot,'recovery')
        before=core.compute_tile(flat,0,16,16,16)
        job=make_job(snapshot,'recovery',terrain=True)
        self.assertNotEqual(core.compute_tile(job,0,16,16,16),before)
        self.assertEqual(core.compute_tile(flat,0,16,16,16),before)
        self.assertFalse(core._terrain_enabled)
        self.assertEqual(make_job(snapshot,'smooth',True)['samples'],2)
        self.assertEqual(make_job(snapshot,'smooth',True)['width'],320)

    def test_invalid_terrain_is_rejected(self):
        job=make_job(load_snapshot(DEFAULT_SNAPSHOT),'recovery',True)
        for points in ([],[[0,0],[0,1]],[[0,0],[1,float('nan')]],[[0,0],[31,0]],[[0,0],[1,False]]):
            bad=copy.deepcopy(job);bad['terrain']['points']=points
            with self.assertRaises(ValueError):core.validate_job(bad)
        bad=copy.deepcopy(job);bad['terrain']['version']='other'
        with self.assertRaises(ValueError):core.validate_job(bad)

if __name__=='__main__':unittest.main()
