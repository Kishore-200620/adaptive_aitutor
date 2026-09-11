import { useState, useRef, useCallback } from 'react';
import { MainLayout } from './layouts/MainLayout'
import { MaterialList } from './features/materials/MaterialList'
import { LessonHistory } from './features/lessons/LessonHistory'
import { ConceptTracker } from './features/concepts/ConceptTracker'
import { StudentStateHeader } from './features/student/StudentStateHeader'
import { AiTeacherWorkspace } from './features/teacher/AiTeacherWorkspace'
import { QuestionAnswerArea } from './features/interaction/QuestionAnswerArea'
import type { LessonResponse, TeacherState } from './types/api'
import { eduvaApi, eduvaStreamApi } from './lib/api'
import { storage } from './lib/storage'

export default function App() {
  const [currentView, setCurrentView] = useState<'home' | 'learning_studio'>('home');
  const [sessionData, setSessionData] = useState<LessonResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  // Separate submission guard to prevent double-submit during answer streaming
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fallback logic inside App.tsx
  // To keep things simple, I'll update the handleStartLesson and handleAnswerSubmit to use streams.
// Wait, I need to make sure I add `import { useRef } from 'react';` if it's missing, but it's likely already there for standard React.

  // Global settings
  const [language, setLanguage] = useState<'English' | 'Tamil' | 'Hindi'>('English');
  const [audioEnabled, setAudioEnabled] = useState(true);

  // Home screen state
  const [topic, setTopic] = useState('');
  const [selectedDocument, setSelectedDocument] = useState<{id: number, filename: string} | null>(null);

  // Fallback to 2 if not set in environment
  const studentId = parseInt(import.meta.env.VITE_DEV_STUDENT_ID || '2', 10);
  
  const abortControllerRef = useRef<AbortController | null>(null);

  const handleStartLesson = async () => {
    const finalTopic = topic.trim();
    if (!finalTopic) return;
    
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();
    
    setIsLoading(true);
    setError(null);
    setCurrentView('learning_studio');
    
    // Set provisional session data
    setSessionData({
      session_id: 0,
      lesson_id: 0,
      student_id: studentId,
      topic: finalTopic,
      action: 'teaching',
      concept: '',
      teaching: '', // Will be streamed
      question: '',
      presentation: null,
      audio_url: null,
      state: {
        student_id: studentId,
        topic: finalTopic,
        language: language,
        planned_concepts: [],
        current_concept_index: 0,
        current_concept: null,
        mastery_score: 0,
        difficulty_level: 'beginner',
        teaching_strategy: 'direct_explanation',
        current_phase: 'introduction',
        last_question: null,
        last_answer: null,
        last_evaluation: null,
        concepts_completed: [],
        concepts_struggling: [],
        misconceptions: [],
        needs_reteaching: false,
        attempt_count: 0,
        assessment_active: false
      }
    });

    try {
      await eduvaStreamApi.startLessonStream(
        {
          student_id: studentId,
          topic: finalTopic,
          document_id: selectedDocument?.id,
          language: language
        },
        (chunk) => {
          setSessionData((prev) => {
            if (!prev) return prev;
            return {
              ...prev,
              teaching: prev.teaching + chunk
            };
          });
        },
        (response) => {
          setSessionData(response);
          // Save minimal metadata to local storage
          storage.saveSession({
            session_id: response.session_id,
            topic: response.topic || finalTopic || 'Lesson',
            concept: response.concept,
            last_updated: new Date().toISOString()
          });
          setIsLoading(false);
        },
        async (streamErr: Error, hasReceivedData: boolean) => {
          console.warn("Stream failed", streamErr);
          
          if (hasReceivedData) {
            console.log("Stream failed but data was received. No fallback needed for start lesson as we don't want to duplicate lesson creation. Refresh to try again.");
            setError('Stream disconnected during startup. Please refresh the page.');
          } else {
            console.log("Stream failed before any data was received. Falling back to sync API.");
            try {
               const fallbackResponse = await eduvaApi.startLesson({
                 student_id: studentId,
                 topic: finalTopic,
                 document_id: selectedDocument?.id,
                 language: language
               });
               setSessionData(fallbackResponse);
               storage.saveSession({
                 session_id: fallbackResponse.session_id,
                 topic: fallbackResponse.topic || finalTopic || 'Lesson',
                 concept: fallbackResponse.concept,
                 last_updated: new Date().toISOString()
               });
            } catch (syncErr: unknown) {
               const e = syncErr as Error;
               setError(e.message || 'Failed to start lesson');
            }
          }
          setIsLoading(false);
        },
        (presentationData) => {
          setSessionData((prev) => {
            if (!prev) return prev;
            return {
              ...prev,
              presentation: presentationData
            };
          });
        },
        abortControllerRef.current.signal
      );
    } catch (err: unknown) {
      const e = err as Error;
      if (e.name !== 'AbortError') {
        setError(e.message || 'Failed to start lesson');
        setIsLoading(false);
      }
    }
  };

  const handleContinueSession = async (sessionId: number) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await eduvaApi.recoverSession(sessionId);
      setSessionData(response);
      setCurrentView('learning_studio');
    } catch (err: unknown) {
      const e = err as Error;
      setError(e.message || 'Failed to restore lesson. It may have expired or been deleted.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleAnswerSubmit = useCallback(async (answer: string) => {
    // Prevent double-submission
    if (!sessionData || isSubmitting || isLoading) return;
    
    // Capture the current state BEFORE clearing UI — needed for fallback
    const stateToSend = { ...sessionData.state, language: language };
    const sessionIdToSend = sessionData.session_id;
    const currentTopic = sessionData.topic;
    
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();
    
    setIsSubmitting(true);
    setError(null);
    
    // Clear previous teaching display but keep state authoritative
    setSessionData((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        teaching: '',
        question: '',
        presentation: null,
        audio_url: null,
        // Keep evaluation from previous round visible until new one arrives
      };
    });
    
    try {
      await eduvaStreamApi.submitAnswerStream(
        {
          session_id: sessionIdToSend,
          state: stateToSend,
          answer: answer
        },
        (chunk) => {
          setSessionData((prev) => {
            if (!prev) return prev;
            return {
              ...prev,
              teaching: prev.teaching + chunk
            };
          });
        },
        (response) => {
          // Replace entire state with authoritative backend response
          // Do NOT call /lessons/next automatically
          setSessionData(response);
          storage.saveSession({
            session_id: response.session_id,
            topic: response.topic || currentTopic || 'Lesson',
            concept: response.concept,
            last_updated: new Date().toISOString()
          });
          setIsSubmitting(false);
        },
        async (streamErr: Error, hasReceivedData: boolean) => {
          console.warn("Stream failed", streamErr);
          
          if (hasReceivedData) {
            console.log("Stream failed but data was received. Recovering session instead of resubmitting.");
            try {
              const recoveredSession = await eduvaApi.recoverSession(sessionIdToSend);
              setSessionData(recoveredSession);
              storage.saveSession({
                session_id: recoveredSession.session_id,
                topic: recoveredSession.topic || currentTopic || 'Lesson',
                concept: recoveredSession.concept,
                last_updated: new Date().toISOString()
              });
            } catch (recoverErr: unknown) {
              const e = recoverErr as Error;
              setError('Stream disconnected and recovery failed: ' + e.message);
            }
          } else {
            console.log("Stream failed before any data was received. Falling back to sync API.");
            try {
              // Use captured state (before UI clear) for reliable fallback
              const fallbackResponse = await eduvaApi.submitAnswer({
                session_id: sessionIdToSend,
                state: stateToSend,
                answer: answer
              });
              setSessionData(fallbackResponse);
              storage.saveSession({
                session_id: fallbackResponse.session_id,
                topic: fallbackResponse.topic || currentTopic || 'Lesson',
                concept: fallbackResponse.concept,
                last_updated: new Date().toISOString()
              });
            } catch (syncErr: unknown) {
              const e = syncErr as Error;
              setError(e.message || 'Failed to submit answer');
            }
          }
          setIsSubmitting(false);
        },
        (presentationData) => {
          setSessionData((prev) => {
            if (!prev) return prev;
            return {
              ...prev,
              presentation: presentationData
            };
          });
        },
        abortControllerRef.current.signal
      );
      
    } catch (err: unknown) {
      const e = err as Error;
      if (e.name !== 'AbortError') {
        setError(e.message || 'Failed to submit answer');
        setIsSubmitting(false);
      }
    }
  }, [sessionData, isSubmitting, isLoading, language]);

  const handleLanguageChange = async (newLang: 'English' | 'Tamil' | 'Hindi') => {
    setLanguage(newLang);
    if (!sessionData) return;
    
    setIsLoading(true);
    setError(null);
    try {
      const response = await eduvaApi.changeLanguage(sessionData.session_id, newLang);
      setSessionData(response);
    } catch (err: unknown) {
      const e = err as Error;
      setError(e.message || 'Failed to change language');
    } finally {
      setIsLoading(false);
    }
  };

  const activeState: Partial<TeacherState> = sessionData?.state || {};

  // Helper: extract string from last_evaluation field which may be string or object
  const getEvaluationDisplay = () => {
    if (sessionData?.interaction_type === 'clarification') return null;
    if (!sessionData?.evaluation) return null;
    const ev = sessionData.evaluation;
    return {
      correctness: ev.correctness || '',
      feedback: ev.feedback || '',
      score: typeof ev.score === 'number' ? ev.score : 0,
    };
  };

  const evaluationDisplay = getEvaluationDisplay();

  const sidebarContent = (
    <>
      <MaterialList 
        onSelectMaterial={(docId, filename) => setSelectedDocument({ id: docId, filename })} 
        disabled={isLoading} 
      />
      <LessonHistory onContinueSession={handleContinueSession} disabled={isLoading} />
      <ConceptTracker state={activeState} />
    </>
  );

  if (currentView === 'home') {
    return (
      <MainLayout
        sidebarContent={sidebarContent}
        headerContent={<div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>EDUVA</div>}
        interactionContent={null}
      >
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          padding: '2rem',
          position: 'relative'
        }}>
          {isLoading && (
            <div style={{ position: 'absolute', top: 0, left: 0, right: 0, zIndex: 10, margin: '1rem', color: 'var(--primary-color)', backgroundColor: '#eff6ff', padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)', border: '1px solid #bfdbfe', textAlign: 'center' }}>
              Loading lesson...
            </div>
          )}
          
          {selectedDocument && (
            <div style={{
              marginBottom: '1.5rem',
              padding: '0.75rem 1rem',
              backgroundColor: '#f8fafc',
              border: '1px solid #cbd5e1',
              borderRadius: 'var(--radius-md)',
              display: 'flex',
              alignItems: 'center',
              gap: '1rem',
              width: '100%',
              maxWidth: '500px'
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
                  Supporting Material
                </div>
                <div style={{ fontSize: '0.875rem', fontWeight: 500, color: 'var(--primary-color)' }}>
                  {selectedDocument.filename}
                </div>
              </div>
              <button
                onClick={() => setSelectedDocument(null)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  fontSize: '1.25rem',
                  lineHeight: 1
                }}
                title="Remove"
              >
                ×
              </button>
            </div>
          )}
          
          <h2 style={{ fontSize: '1.5rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '1.5rem' }}>
            What do you want to learn?
          </h2>
          
          <div style={{ display: 'flex', gap: '0.5rem', width: '100%', maxWidth: '500px' }}>
            <input 
              type="text" 
              placeholder="e.g. Binary Search" 
              value={topic} 
              onChange={e => setTopic(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleStartLesson()}
              disabled={isLoading}
              style={{
                flex: 1,
                padding: '0.75rem 1rem',
                fontSize: '1rem',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-color)',
                outline: 'none',
                boxShadow: '0 1px 2px rgba(0,0,0,0.05)'
              }}
            />
            <button 
              onClick={() => handleStartLesson()}
              disabled={isLoading || !topic.trim()}
              style={{
                padding: '0.75rem 1.5rem',
                fontSize: '1rem',
                fontWeight: 600,
                backgroundColor: 'var(--primary-color)',
                color: 'white',
                border: 'none',
                borderRadius: 'var(--radius-md)',
                cursor: isLoading || !topic.trim() ? 'not-allowed' : 'pointer',
                opacity: isLoading || !topic.trim() ? 0.7 : 1
              }}
            >
              Start Learning
            </button>
          </div>
          
          {error && (
            <div style={{ marginTop: '1rem', color: 'var(--danger-color)', backgroundColor: '#fef2f2', padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)', border: '1px solid #fecaca', width: '100%', maxWidth: '500px' }}>
              {error}
            </div>
          )}
        </div>
      </MainLayout>
    );
  }

  // ── Lesson Completion View ────────────────────────────────────────────
  if (sessionData?.action === 'completed') {
    const completedConcepts: string[] = sessionData.state?.concepts_completed || [];
    const strugglingConcepts: string[] = sessionData.state?.concepts_struggling || [];
    const finalScore = sessionData.state?.mastery_score ?? 0;
    const topic = sessionData.topic || sessionData.state?.topic || 'Lesson';

    return (
      <MainLayout
        sidebarContent={sidebarContent}
        headerContent={
          <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>EDUVA</div>
        }
        interactionContent={null}
      >
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          padding: '2rem',
          gap: '1.5rem',
          overflowY: 'auto',
        }}>
          {/* Trophy icon */}
          <div style={{ fontSize: '4rem', lineHeight: 1 }}>🎓</div>

          <div style={{ textAlign: 'center' }}>
            <h1 style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 0.5rem' }}>
              Lesson Complete!
            </h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '1.05rem', margin: 0 }}>
              Great work on <strong>{topic}</strong>
            </p>
          </div>

          {/* Score card */}
          <div style={{
            backgroundColor: finalScore >= 0.8 ? '#f0fdf4' : finalScore >= 0.5 ? '#fefce8' : '#fef2f2',
            border: `1px solid ${finalScore >= 0.8 ? '#bbf7d0' : finalScore >= 0.5 ? '#fde68a' : '#fecaca'}`,
            borderRadius: 'var(--radius-lg)',
            padding: '1.5rem 2.5rem',
            textAlign: 'center',
            minWidth: '200px',
          }}>
            <div style={{ fontSize: '0.8rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
              Final Mastery Score
            </div>
            <div style={{ fontSize: '3rem', fontWeight: 800, color: finalScore >= 0.8 ? '#15803d' : finalScore >= 0.5 ? '#92400e' : '#b91c1c', lineHeight: 1 }}>
              {Math.round(finalScore * 100)}%
            </div>
          </div>

          {/* Concepts breakdown */}
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', justifyContent: 'center', width: '100%', maxWidth: '600px' }}>
            {completedConcepts.length > 0 && (
              <div style={{
                flex: 1,
                minWidth: '200px',
                backgroundColor: 'white',
                border: '1px solid #bbf7d0',
                borderRadius: 'var(--radius-md)',
                padding: '1rem',
              }}>
                <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#15803d', marginBottom: '0.5rem', textTransform: 'uppercase' }}>
                  ✓ Strong Areas
                </div>
                <ul style={{ margin: 0, paddingLeft: '1.2rem', color: 'var(--text-primary)', fontSize: '0.9rem', lineHeight: 1.8 }}>
                  {completedConcepts.map(c => <li key={c}>{c}</li>)}
                </ul>
              </div>
            )}

            {strugglingConcepts.length > 0 && (
              <div style={{
                flex: 1,
                minWidth: '200px',
                backgroundColor: 'white',
                border: '1px solid #fde68a',
                borderRadius: 'var(--radius-md)',
                padding: '1rem',
              }}>
                <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#92400e', marginBottom: '0.5rem', textTransform: 'uppercase' }}>
                  ⚠ Needs Review
                </div>
                <ul style={{ margin: 0, paddingLeft: '1.2rem', color: 'var(--text-primary)', fontSize: '0.9rem', lineHeight: 1.8 }}>
                  {strugglingConcepts.map(c => <li key={c}>{c}</li>)}
                </ul>
              </div>
            )}

            {completedConcepts.length === 0 && strugglingConcepts.length === 0 && (
              <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                Session data will be available in your progress history.
              </div>
            )}
          </div>

          {/* Last evaluation feedback if present */}
          {sessionData.evaluation?.feedback && (
            <div style={{
              maxWidth: '500px',
              width: '100%',
              backgroundColor: '#f8fafc',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-md)',
              padding: '1rem',
              fontSize: '0.9rem',
              color: 'var(--text-secondary)',
              lineHeight: 1.6,
              textAlign: 'center',
            }}>
              {sessionData.evaluation.feedback}
            </div>
          )}

          {/* Actions */}
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', justifyContent: 'center' }}>
            <button
              onClick={() => {
                setCurrentView('home');
                setSessionData(null);
                setTopic('');
              }}
              style={{
                padding: '0.75rem 2rem',
                backgroundColor: 'var(--primary-color)',
                color: 'white',
                border: 'none',
                borderRadius: 'var(--radius-md)',
                fontWeight: 600,
                fontSize: '1rem',
                cursor: 'pointer',
              }}
            >
              ← Back to Learning
            </button>
            <button
              onClick={() => {
                setSessionData(null);
                setTopic('');
                setCurrentView('home');
              }}
              style={{
                padding: '0.75rem 2rem',
                backgroundColor: 'transparent',
                color: 'var(--primary-color)',
                border: '1px solid var(--primary-color)',
                borderRadius: 'var(--radius-md)',
                fontWeight: 600,
                fontSize: '1rem',
                cursor: 'pointer',
              }}
            >
              Start New Topic
            </button>
          </div>
        </div>
      </MainLayout>
    );
  }

  // ── Learning Studio View ──────────────────────────────────────────────
  return (
    <MainLayout
      sidebarContent={sidebarContent}
      headerContent={
        <div style={{ display: 'flex', alignItems: 'center', width: '100%' }}>
          <button 
            onClick={() => {
              setCurrentView('home');
              setSessionData(null);
            }}
            style={{
              padding: '0.5rem 1rem',
              backgroundColor: 'transparent',
              border: 'none',
              color: 'var(--text-secondary)',
              fontWeight: 500,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              marginRight: 'auto'
            }}
          >
            ← Back to Learning
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginRight: '1rem' }}>
            <button
              onClick={() => setAudioEnabled(!audioEnabled)}
              style={{
                padding: '0.5rem 0.75rem',
                backgroundColor: audioEnabled ? '#e0f2fe' : '#f1f5f9',
                border: '1px solid',
                borderColor: audioEnabled ? '#bae6fd' : '#cbd5e1',
                borderRadius: 'var(--radius-md)',
                color: audioEnabled ? '#0284c7' : '#64748b',
                fontWeight: 500,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                fontSize: '0.875rem'
              }}
            >
              {audioEnabled ? '🔊 Audio On' : '🔇 Audio Off'}
            </button>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', fontWeight: 500 }}>Language:</span>
              <select
                value={language}
                onChange={(e) => handleLanguageChange(e.target.value as 'English' | 'Tamil' | 'Hindi')}
                style={{
                  padding: '0.4rem 0.75rem',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-color)',
                  backgroundColor: 'white',
                  fontSize: '0.875rem',
                  fontWeight: 500,
                  color: 'var(--text-primary)',
                  cursor: 'pointer',
                  outline: 'none'
                }}
              >
                <option value="English">English</option>
                <option value="Tamil">தமிழ்</option>
                <option value="Hindi">हिन्दी</option>
              </select>
            </div>
          </div>
          <StudentStateHeader state={activeState} />
        </div>
      }
      interactionContent={
        <>
          {/* Evaluation feedback display — shown after answer is evaluated */}
          {evaluationDisplay && (
            <div style={{
              padding: '0.75rem 1rem',
              marginBottom: '0.5rem',
              borderRadius: 'var(--radius-md)',
              backgroundColor:
                evaluationDisplay.correctness === 'correct' ? '#f0fdf4' :
                evaluationDisplay.correctness === 'partial' ? '#fefce8' : '#fef2f2',
              border: `1px solid ${
                evaluationDisplay.correctness === 'correct' ? '#bbf7d0' :
                evaluationDisplay.correctness === 'partial' ? '#fde68a' : '#fecaca'
              }`,
              fontSize: '0.875rem',
              lineHeight: 1.5,
            }}>
              <div style={{ fontWeight: 600, marginBottom: '0.25rem', color:
                evaluationDisplay.correctness === 'correct' ? '#15803d' :
                evaluationDisplay.correctness === 'partial' ? '#92400e' : '#b91c1c'
              }}>
                {evaluationDisplay.correctness === 'correct' ? '✓ Correct' :
                 evaluationDisplay.correctness === 'partial' ? '◑ Partially Correct' : '✗ Incorrect'}
                {' '}({Math.round(evaluationDisplay.score * 100)}%)
              </div>
              <div style={{ color: 'var(--text-secondary)' }}>{evaluationDisplay.feedback}</div>
            </div>
          )}
          <QuestionAnswerArea 
            question={sessionData?.question || null}
            onSubmit={handleAnswerSubmit}
            disabled={isSubmitting || !sessionData?.question}
          />
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', position: 'relative' }}>
        {error && (
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, zIndex: 10, margin: '1rem', color: 'var(--danger-color)', backgroundColor: '#fef2f2', padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)', border: '1px solid #fecaca' }}>
            {error}
          </div>
        )}
        
        {sessionData && (
          <AiTeacherWorkspace 
            teachingText={sessionData.teaching || ''}
            presentation={sessionData.presentation || null}
            audioUrl={sessionData.audio_url || null}
            audioEnabled={audioEnabled}
          />
        )}
        
        {isSubmitting && (
          <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(255,255,255,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ padding: '0.5rem 1rem', backgroundColor: 'white', borderRadius: 'var(--radius-md)', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)', color: 'var(--primary-color)', fontWeight: 500 }}>
              Evaluating...
            </span>
          </div>
        )}
        {isLoading && !isSubmitting && (
          <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(255,255,255,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ padding: '0.5rem 1rem', backgroundColor: 'white', borderRadius: 'var(--radius-md)', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)', color: 'var(--primary-color)', fontWeight: 500 }}>
              Thinking...
            </span>
          </div>
        )}
      </div>
    </MainLayout>
  )
}
