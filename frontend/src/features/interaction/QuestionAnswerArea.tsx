import React, { useState } from 'react';
interface QuestionAnswerAreaProps {
  question: string | null;
  onSubmit: (answer: string) => void;
  disabled?: boolean;
}

export function QuestionAnswerArea({ question, onSubmit, disabled }: QuestionAnswerAreaProps) {
  const [answer, setAnswer] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (answer.trim() && !disabled) {
      onSubmit(answer);
      setAnswer('');
    }
  };

  return (
    <div className="interaction-container">
      <div className="question-text">
        {question || "Wait for the teacher's question..."}
      </div>
      
      <form className="answer-form" onSubmit={handleSubmit}>
        <input 
          type="text"
          className="answer-input"
          placeholder="Type your answer or ask a question..."
          value={answer}
          onChange={e => setAnswer(e.target.value)}
          disabled={disabled || !question}
        />
        <button 
          type="submit" 
          className="btn"
          disabled={disabled || !question || !answer.trim()}
        >
          Send
        </button>
      </form>
    </div>
  );
}
