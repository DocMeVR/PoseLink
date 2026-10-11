"""Unit tests for the bone-name logic (pure Python, no Blender):  python -m unittest discover tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bones  # noqa: E402

REDHOOD_BASE = ["Hips", "Spine", "Chest", "Neck", "Head", "LeftEye", "RightEye", "Shoulder_L", "UpperArm_L",
                "LowerArm_L", "Wrist_L", "Thunb1_L", "Thunb2_L", "Thunb3_L", "Index1_L", "Index2_L", "Index3_L",
                "Little1_L", "Shoulder_R", "UpperArm_R", "LowerArm_R", "Wrist_R", "UpperLeg_L", "LowerLeg_L",
                "Foot_L", "Toe_L", "UpperLeg_R", "LowerLeg_R", "Foot_R", "Toe_R", "FrontChest_L", "BackHair_1_1"]
MIXAMO = ["mixamorig:Hips", "mixamorig:Spine", "mixamorig:Spine1", "mixamorig:Spine2", "mixamorig:Neck",
          "mixamorig:Head", "mixamorig:LeftShoulder", "mixamorig:LeftArm", "mixamorig:LeftForeArm",
          "mixamorig:LeftHand", "mixamorig:LeftHandThumb1", "mixamorig:LeftHandThumb2", "mixamorig:LeftHandThumb3",
          "mixamorig:LeftHandThumb4", "mixamorig:LeftUpLeg", "mixamorig:LeftLeg", "mixamorig:LeftFoot",
          "mixamorig:LeftToeBase", "mixamorig:RightUpLeg", "mixamorig:RightLeg"]
VRM = ["J_Bip_C_Hips", "J_Bip_C_Spine", "J_Bip_C_Chest", "J_Bip_C_UpperChest", "J_Bip_C_Neck", "J_Bip_C_Head",
       "J_Bip_L_Shoulder", "J_Bip_L_UpperArm", "J_Bip_L_LowerArm", "J_Bip_L_Hand", "J_Bip_L_Thumb1",
       "J_Bip_L_UpperLeg", "J_Bip_L_LowerLeg", "J_Bip_L_Foot", "J_Bip_L_ToeBase", "J_Sec_Hair1_01"]
CATS = ["Hips", "Spine", "Chest", "Neck", "Head", "Left shoulder", "Left arm", "Left elbow", "Left wrist",
        "Left leg", "Left knee", "Left ankle", "Left toe", "Right leg", "Right knee", "Eye_L", "Eye_R"]
UNITY = ["Hips", "Spine", "Chest", "UpperChest", "Neck", "Head", "LeftShoulder", "LeftUpperArm", "LeftLowerArm",
         "LeftHand", "LeftUpperLeg", "LeftLowerLeg", "LeftFoot", "LeftToes", "RightUpperLeg"]
BLENDER = ["hips", "spine", "chest", "neck", "head", "shoulder.L", "upper_arm.L", "forearm.L", "hand.L",
           "thigh.L", "shin.L", "foot.L", "toe.L", "thigh.R"]


class RoleTests(unittest.TestCase):
    def roles(self, names):
        return bones.humanoid_roles(names)

    def test_redhood_avatar(self):
        r = self.roles(REDHOOD_BASE)
        self.assertEqual(r["Hips"], "Hips")
        self.assertEqual(r["UpperArm_L"], "LeftUpperArm")
        self.assertEqual(r["LowerArm_R"], "RightLowerArm")
        self.assertEqual(r["Wrist_L"], "LeftHand")
        self.assertEqual(r["UpperLeg_L"], "LeftUpperLeg")
        self.assertEqual(r["LowerLeg_R"], "RightLowerLeg")
        self.assertEqual(r["Toe_R"], "RightToes")
        self.assertEqual(r["Shoulder_L"], "LeftShoulder")
        self.assertEqual(r["Thunb1_L"], "LeftThumbProximal")       # typo'd 'Thunb' on this base
        self.assertEqual(r["Thunb3_L"], "LeftThumbDistal")
        self.assertEqual(r["LeftEye"], "LeftEye")
        self.assertNotIn("FrontChest_L", r)                         # breast jiggle bone, not humanoid
        self.assertNotIn("BackHair_1_1", r)

    def test_mixamo_leg_means_lower_leg(self):
        r = self.roles(MIXAMO)
        self.assertEqual(r["mixamorig:LeftArm"], "LeftUpperArm")
        self.assertEqual(r["mixamorig:LeftForeArm"], "LeftLowerArm")
        self.assertEqual(r["mixamorig:LeftUpLeg"], "LeftUpperLeg")
        self.assertEqual(r["mixamorig:LeftLeg"], "LeftLowerLeg")    # Mixamo 'Leg' = shin
        self.assertEqual(r["mixamorig:Spine1"], "Chest")
        self.assertEqual(r["mixamorig:Spine2"], "UpperChest")
        self.assertEqual(r["mixamorig:LeftToeBase"], "LeftToes")
        self.assertEqual(r["mixamorig:LeftHandThumb1"], "LeftThumbProximal")
        self.assertNotIn("mixamorig:LeftHandThumb4", r)            # end bone

    def test_vrm(self):
        r = self.roles(VRM)
        self.assertEqual(r["J_Bip_C_Hips"], "Hips")
        self.assertEqual(r["J_Bip_C_UpperChest"], "UpperChest")
        self.assertEqual(r["J_Bip_L_UpperArm"], "LeftUpperArm")
        self.assertEqual(r["J_Bip_L_ToeBase"], "LeftToes")
        self.assertNotIn("J_Sec_Hair1_01", r)

    def test_cats_leg_means_upper_leg(self):
        r = self.roles(CATS)
        self.assertEqual(r["Left arm"], "LeftUpperArm")
        self.assertEqual(r["Left elbow"], "LeftLowerArm")
        self.assertEqual(r["Left wrist"], "LeftHand")
        self.assertEqual(r["Left leg"], "LeftUpperLeg")             # Cats 'leg' = thigh
        self.assertEqual(r["Left knee"], "LeftLowerLeg")
        self.assertEqual(r["Left ankle"], "LeftFoot")
        self.assertEqual(r["Eye_L"], "LeftEye")

    def test_unity_and_blender_names(self):
        r = self.roles(UNITY)
        self.assertEqual(r["LeftUpperArm"], "LeftUpperArm")
        self.assertEqual(r["LeftToes"], "LeftToes")
        r = self.roles(BLENDER)
        self.assertEqual(r["upper_arm.L"], "LeftUpperArm")
        self.assertEqual(r["forearm.L"], "LeftLowerArm")
        self.assertEqual(r["thigh.R"], "RightUpperLeg")
        self.assertEqual(r["shin.L"], "LeftLowerLeg")

    def test_lookalikes_are_not_humanoid(self):
        r = self.roles(["Hips", "CollarSeam", "Cape_0_1", "Ear_L", "Skirt_L_1", "HeadTop", "Chest_Ribbon"])
        for n in ("CollarSeam", "Cape_0_1", "Ear_L", "Skirt_L_1", "HeadTop", "Chest_Ribbon"):
            self.assertNotIn(n, r)


class MatchTests(unittest.TestCase):
    def test_exact(self):
        m = bones.match_bones(["Hips", "Spine", "Cape_0_1"], ["Hips", "Spine", "Chest"])
        self.assertEqual(m["Hips"], ("Hips", "exact"))
        self.assertNotIn("Cape_0_1", m)

    def test_prefix_suffix_and_duplicates(self):
        outfit = ["RH_Hips", "RH_Spine", "RH_Chest", "RH_Neck", "Head.001", "Skirt_1"]
        base = ["Hips", "Spine", "Chest", "Neck", "Head"]
        m = bones.match_bones(outfit, base)
        self.assertEqual(m["RH_Hips"], ("Hips", "affix"))
        self.assertEqual(m["RH_Neck"], ("Neck", "affix"))
        self.assertEqual(m["Head.001"], ("Head", "affix"))
        self.assertNotIn("Skirt_1", m)

    def test_humanoid_across_naming_schemes(self):
        m = bones.match_bones(MIXAMO, REDHOOD_BASE)
        self.assertEqual(m["mixamorig:LeftForeArm"], ("LowerArm_L", "humanoid"))
        self.assertEqual(m["mixamorig:LeftLeg"], ("LowerLeg_L", "humanoid"))
        self.assertEqual(m["mixamorig:LeftHandThumb1"], ("Thunb1_L", "humanoid"))
        m = bones.match_bones(CATS, REDHOOD_BASE)
        self.assertEqual(m["Left leg"], ("UpperLeg_L", "humanoid"))
        self.assertEqual(m["Left ankle"], ("Foot_L", "humanoid"))

    def test_overrides_win(self):
        m = bones.match_bones(["Hips", "Bust_L"], ["Hips", "FrontChest_L"], overrides={"Bust_L": "FrontChest_L"})
        self.assertEqual(m["Bust_L"], ("FrontChest_L", "manual"))

    def test_override_to_nothing_unlinks(self):
        m = bones.match_bones(["Hips", "Spine"], ["Hips", "Spine"], overrides={"Spine": ""})
        self.assertNotIn("Spine", m)


if __name__ == "__main__":
    unittest.main()
