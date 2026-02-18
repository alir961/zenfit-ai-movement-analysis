# Post-Process Pipeline

## Steps
1. Build raw17 joints from RTMW3D output.
2. Map raw17 to humanoid with explicit placeholders.
3. Compute max IK chain length from ankle -> head chains.
4. Proportion regularization:
   - choose dominant limb lengths,
   - rescale left/right siblings,
   - preserve local segment directions.
5. Estimate `Upper` anchor and normalize pose around it.
6. Compute orientation features:
   - forward surface vector,
   - alignment against `(1,0,1)`,
   - yaw around Y axis.
7. Compute key joint angles (elbows, knees, spine).
8. Build feature vector and update online Gaussian stats.

## Output Fields
- `pose_normalized.ik_max_length`
- `postprocess.regularization.limb_lengths_pre`
- `postprocess.regularization.limb_lengths_post`
- `postprocess.surface_vector`
- `postprocess.yaw_deg`
- `postprocess.joint_angles_deg`
