"""Unit tests for bone name matching (plain Python, no Blender):

    python -m unittest discover -s tests -p "test_bone_names.py"
"""
import importlib.util
import os
import unittest

_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pose_link", "bone_names.py")
_spec = importlib.util.spec_from_file_location("bone_names", _PATH)
bone_names = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bone_names)

BODY = ["Hips", "Spine", "Chest", "Neck", "Head", "LeftEye", "RightEye", "Shoulder_L", "UpperArm_L",
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
ROLE_NAMES = ["Hips", "Spine", "Chest", "UpperChest", "Neck", "Head", "LeftShoulder", "LeftUpperArm",
              "LeftLowerArm", "LeftHand", "LeftUpperLeg", "LeftLowerLeg", "LeftFoot", "LeftToes", "RightUpperLeg"]
RIGIFY = ["hips", "spine", "chest", "neck", "head", "shoulder.L", "upper_arm.L", "forearm.L", "hand.L",
          "thigh.L", "shin.L", "foot.L", "toe.L", "thigh.R"]


class HumanoidRoleTests(unittest.TestCase):
    """The roles let the built-in test poses find the arms and legs on any rig."""

    def test_typical_character(self):
        roles = bone_names.humanoid_roles(BODY)
        self.assertEqual(roles["Hips"], "Hips")
        self.assertEqual(roles["UpperArm_L"], "LeftUpperArm")
        self.assertEqual(roles["LowerArm_R"], "RightLowerArm")
        self.assertEqual(roles["Wrist_L"], "LeftHand")
        self.assertEqual(roles["UpperLeg_L"], "LeftUpperLeg")
        self.assertEqual(roles["LowerLeg_R"], "RightLowerLeg")
        self.assertEqual(roles["Toe_R"], "RightToes")
        self.assertEqual(roles["Shoulder_L"], "LeftShoulder")
        self.assertEqual(roles["Thunb1_L"], "LeftThumbProximal")
        self.assertEqual(roles["Thunb3_L"], "LeftThumbDistal")
        self.assertEqual(roles["LeftEye"], "LeftEye")
        self.assertNotIn("FrontChest_L", roles)
        self.assertNotIn("BackHair_1_1", roles)

    def test_mixamo_leg_means_lower_leg(self):
        roles = bone_names.humanoid_roles(MIXAMO)
        self.assertEqual(roles["mixamorig:LeftArm"], "LeftUpperArm")
        self.assertEqual(roles["mixamorig:LeftForeArm"], "LeftLowerArm")
        self.assertEqual(roles["mixamorig:LeftUpLeg"], "LeftUpperLeg")
        self.assertEqual(roles["mixamorig:LeftLeg"], "LeftLowerLeg")
        self.assertEqual(roles["mixamorig:Spine1"], "Chest")
        self.assertEqual(roles["mixamorig:Spine2"], "UpperChest")
        self.assertEqual(roles["mixamorig:LeftToeBase"], "LeftToes")
        self.assertEqual(roles["mixamorig:LeftHandThumb1"], "LeftThumbProximal")
        self.assertNotIn("mixamorig:LeftHandThumb4", roles)

    def test_vrm(self):
        roles = bone_names.humanoid_roles(VRM)
        self.assertEqual(roles["J_Bip_C_Hips"], "Hips")
        self.assertEqual(roles["J_Bip_C_UpperChest"], "UpperChest")
        self.assertEqual(roles["J_Bip_L_UpperArm"], "LeftUpperArm")
        self.assertEqual(roles["J_Bip_L_ToeBase"], "LeftToes")
        self.assertNotIn("J_Sec_Hair1_01", roles)

    def test_cats_leg_means_upper_leg(self):
        roles = bone_names.humanoid_roles(CATS)
        self.assertEqual(roles["Left arm"], "LeftUpperArm")
        self.assertEqual(roles["Left elbow"], "LeftLowerArm")
        self.assertEqual(roles["Left wrist"], "LeftHand")
        self.assertEqual(roles["Left leg"], "LeftUpperLeg")
        self.assertEqual(roles["Left knee"], "LeftLowerLeg")
        self.assertEqual(roles["Left ankle"], "LeftFoot")
        self.assertEqual(roles["Eye_L"], "LeftEye")

    def test_role_names_and_rigify(self):
        roles = bone_names.humanoid_roles(ROLE_NAMES)
        self.assertEqual(roles["LeftUpperArm"], "LeftUpperArm")
        self.assertEqual(roles["LeftToes"], "LeftToes")
        roles = bone_names.humanoid_roles(RIGIFY)
        self.assertEqual(roles["upper_arm.L"], "LeftUpperArm")
        self.assertEqual(roles["forearm.L"], "LeftLowerArm")
        self.assertEqual(roles["thigh.R"], "RightUpperLeg")
        self.assertEqual(roles["shin.L"], "LeftLowerLeg")

    def test_lookalikes_are_not_humanoid(self):
        roles = bone_names.humanoid_roles(["Hips", "CollarSeam", "Cape_0_1", "Ear_L", "Skirt_L_1", "HeadTop",
                                           "Chest_Ribbon"])
        for name in ("CollarSeam", "Cape_0_1", "Ear_L", "Skirt_L_1", "HeadTop", "Chest_Ribbon"):
            self.assertNotIn(name, roles)


class MatchTests(unittest.TestCase):
    """Outfit bones are matched to the body's own bone names: the same name, or nearly the same."""

    def test_same_name(self):
        matches = bone_names.match_bones(["Hips", "Spine", "Cape_0_1"], ["Hips", "Spine", "Chest"])
        self.assertEqual(matches["Hips"], ("Hips", "exact"))
        self.assertNotIn("Cape_0_1", matches)

    def test_case_separators_and_duplicate_suffix(self):
        body = ["Hips", "UpperArm_L", "LowerArm_R", "Head"]
        matches = bone_names.match_bones(["hips", "upper_arm.L", "lower-arm R", "Head.001"], body)
        self.assertEqual(matches["hips"], ("Hips", "similar"))
        self.assertEqual(matches["upper_arm.L"], ("UpperArm_L", "similar"))
        self.assertEqual(matches["lower-arm R"], ("LowerArm_R", "similar"))
        self.assertEqual(matches["Head.001"], ("Head", "similar"))

    def test_side_written_another_way(self):
        body = ["UpperArm_L", "UpperArm_R"]
        matches = bone_names.match_bones(["LeftUpperArm", "UpperArm.R"], body)
        self.assertEqual(matches["LeftUpperArm"], ("UpperArm_L", "similar"))
        self.assertEqual(matches["UpperArm.R"], ("UpperArm_R", "similar"))

    def test_sides_never_swap(self):
        matches = bone_names.match_bones(["UpperArm_R"], ["UpperArm_L"])
        self.assertNotIn("UpperArm_R", matches)

    def test_numbers_must_agree(self):
        matches = bone_names.match_bones(["Index2_L"], ["Index1_L", "Index3_L"])
        self.assertNotIn("Index2_L", matches)

    def test_outfit_prefix_or_suffix(self):
        outfit = ["RH_Hips", "RH_Spine", "RH_Chest", "Neck_dress", "Head_dress", "Skirt_1"]
        matches = bone_names.match_bones(outfit, ["Hips", "Spine", "Chest", "Neck", "Head"])
        self.assertEqual(matches["RH_Hips"], ("Hips", "similar"))
        self.assertEqual(matches["RH_Chest"], ("Chest", "similar"))
        self.assertEqual(matches["Neck_dress"], ("Neck", "similar"))
        self.assertNotIn("Skirt_1", matches)

    def test_namespace_prefix(self):
        matches = bone_names.match_bones(["mixamorig:Hips", "mixamorig:LeftFoot"], ["Hips", "Foot_L"])
        self.assertEqual(matches["mixamorig:Hips"], ("Hips", "similar"))
        self.assertEqual(matches["mixamorig:LeftFoot"], ("Foot_L", "similar"))

    def test_other_naming_schemes_are_not_guessed(self):
        # ForeArm / UpLeg are different words than LowerArm / UpperLeg: pick those by hand in Bone Matching
        matches = bone_names.match_bones(MIXAMO, BODY)
        self.assertNotIn("mixamorig:LeftForeArm", matches)
        self.assertNotIn("mixamorig:LeftUpLeg", matches)
        matches = bone_names.match_bones(CATS, BODY)
        self.assertNotIn("Left elbow", matches)

    def test_ambiguous_names_are_left_alone(self):
        matches = bone_names.match_bones(["spine"], ["Spine", "SPINE"])
        self.assertNotIn("spine", matches)

    def test_overrides_win(self):
        matches = bone_names.match_bones(["Hips", "Bust_L"], ["Hips", "FrontChest_L"],
                                         overrides={"Bust_L": "FrontChest_L"})
        self.assertEqual(matches["Bust_L"], ("FrontChest_L", "manual"))

    def test_override_to_nothing_unlinks(self):
        matches = bone_names.match_bones(["Hips", "Spine"], ["Hips", "Spine"], overrides={"Spine": ""})
        self.assertNotIn("Spine", matches)


if __name__ == "__main__":
    unittest.main()
