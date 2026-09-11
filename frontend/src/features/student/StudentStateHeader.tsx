import type { TeacherState } from '../../types/api';

interface StudentStateHeaderProps {
  state: Partial<TeacherState>;
}

export function StudentStateHeader({ state }: StudentStateHeaderProps) {
  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <h1 style={{ fontSize: '1.25rem', fontWeight: 600 }}>Eduva Learning Studio</h1>
        <div style={{ height: '24px', width: '1px', backgroundColor: 'var(--border-color)' }}></div>
        <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>Topic: {state.topic || 'No topic'}</span>
        {state.current_concept && (
          <>
            <div style={{ height: '24px', width: '1px', backgroundColor: 'var(--border-color)' }}></div>
            <span style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--primary-color)' }}>
              {state.current_concept}
            </span>
          </>
        )}
      </div>
      
      <div style={{ display: 'flex', gap: '0.75rem' }}>
        {state.mastery_score !== undefined && (
          <span className="badge badge-blue">
            Mastery: {(state.mastery_score * 100).toFixed(0)}%
          </span>
        )}
        
        {state.difficulty_level && (
          <span className="badge badge-gray">
            Level: {state.difficulty_level}
          </span>
        )}
        
        {state.teaching_strategy && (
          <span className="badge badge-gray">
            Strategy: {state.teaching_strategy.replace('_', ' ')}
          </span>
        )}

        {state.planned_concepts && state.planned_concepts.length > 0 && state.current_concept_index !== undefined && (
          <span className="badge badge-gray" style={{ background: '#dcfce7', color: '#166534' }}>
            Subtopic: {state.current_concept_index + 1} / {state.planned_concepts.length}
          </span>
        )}

        {state.concept_steps_current !== undefined && state.concept_steps_total !== undefined && (
          <span className="badge badge-gray" style={{ background: '#e0e7ff', color: '#3730a3' }}>
            Step: {state.concept_steps_current} / {state.concept_steps_total}
          </span>
        )}

        {state.needs_reteaching && (
          <span className="badge badge-orange">
            Needs Reteaching
          </span>
        )}
      </div>
    </>
  );
}
