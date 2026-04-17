import React, { useState } from 'react';
import { createRun, submitRunClarifications } from '../../services/bmadService';

interface RunContextEvent {
  event_type: string;
  run_id?: number;
  phase?: string;
  context_source?: string;
  context_version?: number;
  old_status?: string;
  new_status?: string;
  reason?: string;
  timestamp?: string;
}

interface RunSnapshot {
  id: number;
  status: string;
  original_input: string;
  resolved_input_context: string | null;
  context_version: number;
  context_events: RunContextEvent[];
  phase_statuses?: Record<string, string>;
  phase_status_badges?: Record<string, string>;
}

const RunInitiationForm: React.FC = () => {
  const [apiSpec, setApiSpec] = useState<string>('');
  const [message, setMessage] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [clarificationQuestions, setClarificationQuestions] = useState<string[]>([]);
  const [clarificationAnswers, setClarificationAnswers] = useState<Record<string, string>>({});
  const [isAwaitingClarification, setIsAwaitingClarification] = useState<boolean>(false);
  const [runId, setRunId] = useState<number | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [latestRun, setLatestRun] = useState<RunSnapshot | null>(null);

  const normalizeQuestions = (questions: string[]): string[] => (
    [...questions].sort((a, b) => a.localeCompare(b))
  );

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (isSubmitting) {
      return;
    }

    setMessage('');
    setError('');
    setClarificationQuestions([]);
    setClarificationAnswers({});
    setIsAwaitingClarification(false);
    setRunId(null);
    setLatestRun(null);

    if (!apiSpec.trim()) {
      setError('API Specification cannot be empty.');
      return;
    }

    try {
      setIsSubmitting(true);
      const response = await createRun(apiSpec);
      const newRun = response.run;
      setRunId(newRun.id);
      setLatestRun(newRun);
      if (response.validation.is_complete) {
        setMessage(`Run initiated successfully! Run ID: ${newRun.id}, Status: ${newRun.status}`);
        setApiSpec('');
        return;
      }

      const clarificationQuestions = Array.isArray(response.validation.clarification_questions)
        ? response.validation.clarification_questions
        : [];
      const orderedQuestions = normalizeQuestions(clarificationQuestions);
      setMessage(
        `Input clarification required before continuation. Run ID: ${newRun.id}, Status: ${newRun.status}`
      );
      setClarificationQuestions(orderedQuestions);
      setClarificationAnswers(
        orderedQuestions.reduce<Record<string, string>>((acc, question) => {
          acc[question] = '';
          return acc;
        }, {})
      );
      setIsAwaitingClarification(true);
    } catch (err) {
      setError('Failed to initiate run. Please try again.');
      console.error(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClarificationChange = (question: string, value: string) => {
    setClarificationAnswers((previous) => ({
      ...previous,
      [question]: value,
    }));
  };

  const handleClarificationSubmit = async () => {
    if (isSubmitting || runId === null) {
      return;
    }

    const hasEmptyAnswer = clarificationQuestions.some(
      (question) => !(clarificationAnswers[question] || '').trim()
    );
    if (hasEmptyAnswer) {
      setError('Please answer all clarification questions before continuing.');
      return;
    }

    try {
      setIsSubmitting(true);
      setError('');
      const response = await submitRunClarifications(
        runId,
        clarificationQuestions.map((question) => ({
          question,
          answer: clarificationAnswers[question] || '',
        }))
      );

      const updatedRun = response.run;
      setLatestRun(updatedRun);
      if (response.validation.is_complete) {
        setMessage(`Run resumed successfully! Run ID: ${updatedRun.id}, Status: ${updatedRun.status}`);
        setClarificationQuestions([]);
        setClarificationAnswers({});
        setIsAwaitingClarification(false);
        setRunId(updatedRun.id);
        return;
      }

      const nextQuestions = normalizeQuestions(
        Array.isArray(response.validation.clarification_questions)
          ? response.validation.clarification_questions
          : []
      );
      setMessage(
        `Clarification responses saved. Additional input is still required. Run ID: ${updatedRun.id}, Status: ${updatedRun.status}`
      );
      setClarificationQuestions(nextQuestions);
      setClarificationAnswers(
        nextQuestions.reduce<Record<string, string>>((acc, question) => {
          acc[question] = clarificationAnswers[question] || '';
          return acc;
        }, {})
      );
      setIsAwaitingClarification(true);
    } catch (err) {
      setError('Failed to submit clarification responses. Please try again.');
      console.error(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxWidth: '500px', margin: '20px auto' }}>
      <h2>Initiate New BMAD Run</h2>
      <textarea
        value={apiSpec}
        onChange={(e) => setApiSpec(e.target.value)}
        placeholder="Enter free-text API specification (e.g., 'Create a Todo API with CRUD operations')"
        rows={10}
        style={{ width: '100%', padding: '8px', border: '1px solid #ccc', borderRadius: '4px' }}
      ></textarea>
      <button
        type="submit"
        disabled={isSubmitting}
        style={{ padding: '10px 15px', backgroundColor: '#007bff', color: 'white', border: 'none', borderRadius: '4px', cursor: isSubmitting ? 'not-allowed' : 'pointer', opacity: isSubmitting ? 0.7 : 1 }}
      >
        Initiate BMAD Run
      </button>
      {message && (
        <p style={{ color: isAwaitingClarification ? '#8a6d3b' : 'green' }}>
          {message}
        </p>
      )}
      {isAwaitingClarification && (
        <p
          style={{
            marginTop: 0,
            marginBottom: 0,
            color: '#8a6d3b',
            fontWeight: 600,
          }}
        >
          Workflow paused: provide clarifications to continue.
        </p>
      )}
      {clarificationQuestions.length > 0 && (
        <div style={{ border: '1px solid #f0ad4e', borderRadius: '4px', padding: '10px', backgroundColor: '#fff8e1' }}>
          <p style={{ marginTop: 0 }}><strong>Clarification questions (in stable order):</strong></p>
          <ul style={{ marginBottom: 10 }}>
            {clarificationQuestions.map((question, index) => (
              <li key={`${question}-${index}`}>
                <p style={{ marginTop: 0, marginBottom: 6 }}>{question}</p>
                <input
                  type="text"
                  value={clarificationAnswers[question] || ''}
                  onChange={(e) => handleClarificationChange(question, e.target.value)}
                  placeholder="Provide clarification response"
                  required
                  style={{ width: '100%', padding: '8px', border: '1px solid #ccc', borderRadius: '4px' }}
                />
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={handleClarificationSubmit}
            disabled={isSubmitting || runId === null}
            style={{ padding: '10px 15px', backgroundColor: '#8a6d3b', color: 'white', border: 'none', borderRadius: '4px', cursor: isSubmitting ? 'not-allowed' : 'pointer', opacity: isSubmitting ? 0.7 : 1 }}
          >
            Submit Clarifications
          </button>
        </div>
      )}
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {latestRun && (
        <section style={{ border: '1px solid #d9edf7', borderRadius: '4px', padding: '10px', backgroundColor: '#f4f9fd' }}>
          <p style={{ marginTop: 0 }}><strong>Original input context</strong></p>
          <p>{latestRun.original_input || '-'}</p>
          <p><strong>Resolved input context</strong></p>
          <p>{latestRun.resolved_input_context || 'Pending clarification.'}</p>
          <p><strong>Context version: {latestRun.context_version}</strong></p>
          {latestRun.phase_statuses && Object.keys(latestRun.phase_statuses).length > 0 && (
            <>
              <p><strong>Phase statuses</strong></p>
              <ul>
                {Object.entries(latestRun.phase_statuses).map(([phase, status]) => (
                  <li key={phase}>
                    {phase}: {latestRun.phase_status_badges?.[status] || status}
                  </li>
                ))}
              </ul>
            </>
          )}
          {Array.isArray(latestRun.context_events) && latestRun.context_events.length > 0 && (
            <ul style={{ marginBottom: 0 }}>
              {latestRun.context_events.map((event, index) => (
                <li key={`${event.event_type}-${event.phase}-${index}`}>
                  {event.event_type}
                  {event.phase ? ` (${event.phase})` : ''}
                  {event.event_type === 'phase-status-changed'
                    ? ` ${event.old_status} -> ${event.new_status} (${event.reason || 'n/a'})`
                    : ` - source: ${event.context_source || 'n/a'}, version: ${event.context_version ?? 'n/a'}`}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </form>
  );
};

export default RunInitiationForm;
