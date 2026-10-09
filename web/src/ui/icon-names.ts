// The Reicon glyphs the interface uses, Outline weight only. Each semantic name maps to
// one icon function from the `reicon` package. Importing the glyphs one by one keeps the
// bundle to a few dozen icons instead of the 2 600 of the full set.

import { AlertTriangle } from "reicon/icons/AlertTriangle";
import { ArrowUpRightSquare } from "reicon/icons/ArrowUpRightSquare";
import { BookOpen } from "reicon/icons/BookOpen";
import { ChartBar } from "reicon/icons/ChartBar";
import { ChatRoundLine } from "reicon/icons/ChatRoundLine";
import { Check } from "reicon/icons/Check";
import { Copy } from "reicon/icons/Copy";
import { Download2 } from "reicon/icons/Download2";
import { Edit } from "reicon/icons/Edit";
import { Gear } from "reicon/icons/Gear";
import { InfoCircle } from "reicon/icons/InfoCircle";
import { Logout } from "reicon/icons/Logout";
import { Moon } from "reicon/icons/Moon";
import { RotateRight } from "reicon/icons/RotateRight";
import { Send } from "reicon/icons/Send";
import { ShieldAlert } from "reicon/icons/ShieldAlert";
import { Stop } from "reicon/icons/Stop";
import { Sun } from "reicon/icons/Sun";
import { Trash2 } from "reicon/icons/Trash2";
import { WifiOff } from "reicon/icons/WifiOff";
import { X } from "reicon/icons/X";

export const ICONS = {
  "arrow-clockwise": RotateRight,
  "arrow-square-out": ArrowUpRightSquare,
  "book-open": BookOpen,
  "chart-bar": ChartBar,
  "chat-circle-text": ChatRoundLine,
  check: Check,
  copy: Copy,
  "download-simple": Download2,
  gear: Gear,
  info: InfoCircle,
  moon: Moon,
  "note-pencil": Edit,
  "paper-plane-right": Send,
  "shield-warning": ShieldAlert,
  "sign-out": Logout,
  stop: Stop,
  sun: Sun,
  trash: Trash2,
  warning: AlertTriangle,
  "wifi-slash": WifiOff,
  x: X,
} as const;

export type IconName = keyof typeof ICONS;
