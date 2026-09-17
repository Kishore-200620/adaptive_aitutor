import type { TeacherState } from '../../types/api';

interface StudentStateHeaderProps {
  state: Partial<TeacherState>;
  leftContent?: React.ReactNode;
  rightContent?: React.ReactNode;
}

export function StudentStateHeader({ state, leftContent, rightContent }: StudentStateHeaderProps) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', width: '100%', gap: '1rem', flexWrap: 'wrap' }}>
      {/* Left Column */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flex: '0 1 auto' }}>
        {leftContent}
      </div>

      {/* Center Column - Topic */}
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: '0.75rem', 
        flex: '1 1 auto',
        justifyContent: 'center',
        minWidth: 0 // enables text truncation in flex child
      }}>
        <h1 style={{ fontSize: '1.1rem', fontWeight: 600, whiteSpace: 'nowrap', margin: 0 }}>EDUVA</h1>
        <div style={{ height: '20px', width: '1px', backgroundColor: 'var(--border-color)' }}></div>
        <div style={{ 
          display: 'flex', 
          flexDirection: 'column', 
          minWidth: 0,
          overflow: 'hidden'
        }}>
          <span style={{ 
            fontSize: '0.9rem', 
            fontWeight: 600, 
            color: 'var(--primary-color)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis'
          }} title={state.topic || 'No topic'}>
            {state.topic || 'No topic'}
          </span>
          {state.current_concept && (
            <span style={{ 
              fontSize: '0.75rem', 
              color: 'var(--text-secondary)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis'
            }} title={state.current_concept}>
              {state.current_concept}
            </span>
          )}
        </div>
      </div>

      {/* Right Column - Controls & Progress */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flex: '0 1 auto', marginLeft: 'auto', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
        {rightContent}
        
        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
          {state.mastery_score !== undefined && (
            <span className="badge badge-blue" style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem' }}>
              {(state.mastery_score * 100).toFixed(0)}%
            </span>
          )}
          
          {state.difficulty_level && (
            <span className="badge badge-gray" style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem' }}>
              Lvl {state.difficulty_level}
            </span>
          )}

          {state.planned_concepts && state.planned_concepts.length > 0 && state.current_concept_index !== undefined && (
            <span className="badge badge-gray" style={{ background: '#dcfce7', color: '#166534', padding: '0.2rem 0.5rem', fontSize: '0.75rem' }}>
              Sub {state.current_concept_index + 1}/{state.planned_concepts.length}
            </span>
          )}

          {state.concept_steps_current !== undefined && state.concept_steps_total !== undefined && (
            <span className="badge badge-gray" style={{ background: '#e0e7ff', color: '#3730a3', padding: '0.2rem 0.5rem', fontSize: '0.75rem' }}>
              Step {state.concept_steps_current}/{state.concept_steps_total}
            </span>
          )}

          {state.needs_reteaching && (
            <span className="badge badge-orange" style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem' }}>
              Review
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
