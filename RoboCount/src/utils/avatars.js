import avatar1 from "../assets/avatars/optimized/avatar1.webp";
import avatar2 from "../assets/avatars/optimized/avatar2.webp";
import avatar3 from "../assets/avatars/optimized/avatar3.webp";
import avatar4 from "../assets/avatars/optimized/avatar4.webp";
import avatar5 from "../assets/avatars/optimized/avatar5.webp";
import avatar6 from "../assets/avatars/optimized/avatar6.webp";
import avatar7 from "../assets/avatars/optimized/avatar7.webp";
import avatar8 from "../assets/avatars/optimized/avatar8.webp";

export const DEFAULT_AVATAR_ID = "1";

export const ROBOT_AVATARS = [
  { id: "1", label: "Avatar 1", src: avatar1, gridSlot: 1 },
  { id: "2", label: "Avatar 2", src: avatar2, gridSlot: 2 },
  { id: "3", label: "Avatar 3", src: avatar3, gridSlot: 3 },
  { id: "4", label: "Avatar 4", src: avatar4, gridSlot: 4 },
  { id: "5", label: "Avatar 5", src: avatar5, gridSlot: 5 },
  { id: "6", label: "Avatar 6", src: avatar6, gridSlot: 6 },
  { id: "7", label: "Avatar 7", src: avatar7, gridSlot: 7 },
  { id: "8", label: "Avatar 8", src: avatar8, gridSlot: 8 },
];

export function getRobotAvatar(avatarId) {
  return ROBOT_AVATARS.find((avatar) => avatar.id === String(avatarId || "")) || ROBOT_AVATARS[0];
}
