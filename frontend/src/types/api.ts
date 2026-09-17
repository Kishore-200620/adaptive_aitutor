export interface TeacherState {
  student_id: number;
  topic: string;
  language: string;
  planned_concepts: string[];
  current_concept_index: number;
  current_concept: string | null;
  mastery_score: number;
  difficulty_level: 'beginner' | 'intermediate' | 'advanced';
  teaching_strategy: 'direct_explanation' | 'guided_discovery' | 'socratic_questioning' | 'worked_example';
  current_phase: 'introduction' | 'explanation' | 'questioning' | 'feedback' | 'reteaching' | 'transition';
  last_question: string | null;
  last_answer: string | null;
  last_evaluation: {
    correctness: string;
    score: number;
    feedback: string;
    misconception: string | null;
  } | null;
  concepts_completed: string[];
  concepts_struggling: string[];
  misconceptions: string[];
  needs_reteaching: boolean;
  attempt_count: number;
  assessment_active: boolean;
  concept_steps_total?: number;
  concept_steps_current?: number;
  concept_history?: any[];
  teaching_cursor?: Record<string, any> | null;
}

export interface VoiceDecision {
  enabled: boolean;
  narration: string;
}

export interface PdfVisualMetadata {
  visual_id: number;
  document_id: number;
  page_number: number;
  visual_type: string;
  asset_url: string | null;
  caption: string | null;
  metadata: Record<string, any>;
}

export interface BlackboardDecision {
  enabled: boolean;
  content: string;
  visual_type: string;
  visual_source: string;
  visual_url: string | null;
  pdf_visual?: PdfVisualMetadata | null;
}

export type TeacherVideoTrigger = 'intro' | 'concept_intro' | 'emphasis' | 'transition' | 'encouragement' | 'completion' | 'none';

export interface TeacherVideoDecision {
  enabled: boolean;
  trigger: TeacherVideoTrigger;
  reason: string | null;
  clip_id: string | null;
  provider: string | null;
  url: string | null;
}

export interface PresentationDecision {
  mode: 'VOICE_ONLY' | 'VOICE_BLACKBOARD' | 'VOICE_TEACHER_VIDEO' | 'VOICE_BLACKBOARD_TEACHER_VIDEO';
  voice: VoiceDecision;
  blackboard: BlackboardDecision;
  teacher_video: TeacherVideoDecision;
}

export interface StartLessonRequest {
  student_id: number;
  topic: string;
  document_id?: number | null;
  language?: string | null;
}

export interface NextStepRequest {
  session_id: number;
  state: TeacherState;
}

export interface AnswerRequest {
  session_id: number;
  state: TeacherState;
  answer: string;
}

export interface LessonResponse {
  session_id: number;
  lesson_id?: number; // Present on start
  student_id?: number; // Present on start
  topic?: string; // Present on start
  action?: 'teaching' | 'completed' | string; 
  concept: string | null;
  teaching: string;
  question: string | null;
  presentation: PresentationDecision | null;
  audio_url: string | null;
  state: TeacherState;
  evaluation?: {
    correctness: string;
    score: number;
    feedback: string;
    misconception: string | null;
  }; // Present on answer
  interaction_type?: 'assessment' | 'clarification';
}

export interface DocumentUploadResponse {
  message: string;
  document_id: number;
  filename: string;
  status: string;
  chunks_created: number;
}
