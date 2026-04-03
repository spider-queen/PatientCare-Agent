export type Patient = {
  id: number;
  patient_code: string;
  full_name: string;
  gender?: string | null;
  date_of_birth?: string | null;
  phone?: string | null;
  id_number?: string | null;
  address?: string | null;
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
};

export type VisitRecord = {
  id: number;
  visit_code: string;
  visit_type: string;
  department?: string | null;
  physician_name?: string | null;
  visit_time: string;
  summary?: string | null;
  notes?: string | null;
};

export type UserProfile = {
  profile_summary?: string | null;
  communication_style?: string | null;
  preferred_topics?: string | null;
  stable_preferences?: string | null;
  source_summary?: string | null;
};

export type MemoryPreference = {
  preferred_name?: string | null;
  response_style?: string | null;
  response_length?: string | null;
  preferred_language?: string | null;
  focus_topics?: string | null;
  additional_preferences?: string | null;
};

export type MemoryEvent = {
  id: number;
  event_type: string;
  event_time: string;
  title: string;
  summary?: string | null;
  source_type: string;
};

export type PatientOverviewResponse = {
  patient: Patient;
  latest_visit?: VisitRecord | null;
  user_profile?: UserProfile | null;
  memory_preference?: MemoryPreference | null;
  recent_memory_events: MemoryEvent[];
};
