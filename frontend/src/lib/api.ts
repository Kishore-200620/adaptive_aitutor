import type { StartLessonRequest, NextStepRequest, AnswerRequest, LessonResponse, DocumentUploadResponse } from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

class ApiError extends Error {
  public status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}

async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  
  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      errorData.detail || `API Request failed with status ${response.status}`
    );
  }

  return response.json();
}

export const eduvaApi = {
  startLesson: (data: StartLessonRequest) => 
    fetchApi<LessonResponse>('/lessons/start', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  nextStep: (data: NextStepRequest) =>
    fetchApi<LessonResponse>('/lessons/next', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  submitAnswer: (data: AnswerRequest) =>
    fetchApi<LessonResponse>('/lessons/answer', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  recoverSession: (sessionId: number) =>
    fetchApi<LessonResponse>(`/lessons/session/${sessionId}`, {
      method: 'GET',
    }),

  getSessions: (studentId: number) =>
    fetchApi<import('./storage').LocalSession[]>(`/lessons/sessions/${studentId}`, {
      method: 'GET',
    }),

  changeLanguage: (sessionId: number, language: string) =>
    fetchApi<LessonResponse>(`/lessons/session/${sessionId}/language`, {
      method: 'POST',
      body: JSON.stringify({ language }),
    }),

  uploadDocument: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    
    // We can't use fetchApi because it sets Content-Type to application/json by default
    // For FormData, we must let the browser set the Content-Type with boundary automatically
    const response = await fetch(`${API_BASE_URL}/documents/upload`, {
      method: 'POST',
      body: formData,
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new ApiError(
        response.status,
        errorData.detail || `Upload failed with status ${response.status}`
      );
    }
    
    return response.json() as Promise<DocumentUploadResponse>;
  },
};

export async function fetchApiStream(
  endpoint: string,
  options: RequestInit,
  onChunk: (chunk: string) => void,
  onComplete: (data: any) => void,
  onError: (error: Error, hasReceivedData: boolean) => void,
  onPresentation?: (data: any) => void
) {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  try {
    const response = await fetch(url, { ...options, headers });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new ApiError(
        response.status,
        errorData.detail || `Stream failed with status ${response.status}`
      );
    }

    if (!response.body) {
      throw new Error('ReadableStream not supported by the browser.');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    let hasReceivedData = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      
      const parts = buffer.split('\n\n');
      buffer = parts.pop() || ''; // Keep the incomplete part in the buffer

      for (const part of parts) {
        if (part.startsWith('data: ')) {
          const dataStr = part.slice(6);
          try {
            const data = JSON.parse(dataStr);
            if (data.type === 'teaching_chunk') {
              hasReceivedData = true;
              onChunk(data.content);
            } else if (data.type === 'complete') {
              hasReceivedData = true;
              onComplete(data.data);
            } else if (data.type === 'error') {
              hasReceivedData = true;
              onError(new Error(data.message), hasReceivedData);
            } else if (data.type === 'presentation' && onPresentation) {
              hasReceivedData = true;
              onPresentation(data.data);
            }
          } catch (e) {
            console.error('Failed to parse SSE event:', part);
          }
        }
      }
    }
  } catch (err) {
    onError(err as Error, false);
  }
}

export const eduvaStreamApi = {
  startLessonStream: (
    data: StartLessonRequest,
    onChunk: (chunk: string) => void,
    onComplete: (data: LessonResponse) => void,
    onError: (error: Error, hasReceivedData: boolean) => void,
    onPresentation?: (data: any) => void,
    signal?: AbortSignal
  ) =>
    fetchApiStream(
      '/lessons/start/stream',
      { method: 'POST', body: JSON.stringify(data), signal },
      onChunk,
      onComplete,
      onError,
      onPresentation
    ),

  submitAnswerStream: (
    data: AnswerRequest,
    onChunk: (chunk: string) => void,
    onComplete: (data: LessonResponse) => void,
    onError: (error: Error, hasReceivedData: boolean) => void,
    onPresentation?: (data: any) => void,
    signal?: AbortSignal
  ) =>
    fetchApiStream(
      '/lessons/answer/stream',
      { method: 'POST', body: JSON.stringify(data), signal },
      onChunk,
      onComplete,
      onError,
      onPresentation
    ),
};
