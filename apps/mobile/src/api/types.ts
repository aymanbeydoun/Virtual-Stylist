export type OwnerKind = "user" | "family_member";

export type FamilyMemberKind = "adult" | "teen" | "kid";

export interface FamilyMember {
  id: string;
  display_name: string;
  kind: FamilyMemberKind;
  birth_year: number | null;
  kid_mode: boolean;
  created_at: string;
}

export interface ColorTag {
  name: string;
  hex: string;
  weight: number;
}

export interface WardrobeItem {
  id: string;
  owner_kind: OwnerKind;
  owner_id: string;
  raw_image_key: string;
  cutout_image_key: string | null;
  thumbnail_key: string | null;
  category: string | null;
  colors: ColorTag[];
  pattern: string | null;
  formality: number | null;
  seasonality: string[];
  needs_review: boolean;
  status: "pending" | "ready" | "failed";
  created_at: string;
}

export interface UploadUrlResponse {
  upload_url: string;
  object_key: string;
  expires_at: string;
}

export type Destination =
  | "office" | "date" | "brunch" | "gym" | "playground"
  | "school" | "travel" | "formal_event" | "casual";

export type Mood = "confident" | "cozy" | "edgy" | "playful" | "minimal" | "romantic";

export interface Outfit {
  id: string;
  destination: string | null;
  mood: string | null;
  rationale: string | null;
  confidence: number | null;
  composite_image_key: string | null;
  items: { slot: string; item: WardrobeItem }[];
  created_at: string;
}

export interface GenerateOutfitResponse {
  outfits: Outfit[];
  weather: { temp_c: number; condition: string; wind_kph: number } | null;
}

export type GapSeverity = "high" | "medium" | "low";
export type GapStatus = "open" | "dismissed" | "resolved";

export interface GapFinding {
  id: string;
  slot: string;
  category_hint: string | null;
  title: string;
  rationale: string | null;
  severity: GapSeverity;
  status: GapStatus;
  search_query: string | null;
  created_at: string;
}

export type TryonStatus = "pending" | "ready" | "failed";

export interface OutfitTryon {
  id: string;
  outfit_id: string;
  base_photo_key: string;
  rendered_image_key: string | null;
  status: TryonStatus;
  model_id: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface BasePhoto {
  base_photo_key: string | null;
}
