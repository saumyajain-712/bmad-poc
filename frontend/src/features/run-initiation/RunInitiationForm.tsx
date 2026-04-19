import React, { useState } from 'react';
import {
  applyPhaseCorrection,
  createRun,
  fetchRun,
  resetRunEnvironment,
  submitRunClarifications,
} from '../../services/bmadService';
import type { Run, RunTimelineEvent } from '../../services/bmadService';
import RunTimeline from '../run-observability/RunTimeline';

type RunSnapshot = Pick<
  Run,
  | 'id'
  | 'status'
  | 'original_input'
  | 'resolved_input_context'
  | 'context_version'
  | 'context_events'
  | 'phase_statuses'
  | 'phase_status_badges'
  | 'current_phase_proposal'
  | 'verification_review'
  | 'final_output_review'
  | 'run_complete'
>;

const sortKeysDeep = (value: unknown): unknown => {
  if (value === null || typeof value !== 'object') {
    return value;
  }
  if (Array.isArray(value)) {
    return value.map(sortKeysDeep);
  }
  const obj = value as Record<string, unknown>;
  const sorted: Record<string, unknown> = {};
  for (const key of Object.keys(obj).sort()) {
    sorted[key] = sortKeysDeep(obj[key]);
  }
  return sorted;
};

const artifactsEqual = (
  left: Record<string, unknown> | undefined,
  right: Record<string, unknown> | undefined
): boolean => {
  if (left === right) {
    return true;
  }
  if (left === undefined || right === undefined) {
    return false;
  }
  return JSON.stringify(sortKeysDeep(left)) === JSON.stringify(sortKeysDeep(right));
};

const optionalEqual = (a: string | null | undefined, b: string | null | undefined): boolean => a === b;

const areEventsEqual = (left: RunTimelineEvent, right: RunTimelineEvent): boolean => (
  left.event_type === right.event_type
  && left.run_id === right.run_id
  && optionalEqual(left.phase, right.phase)
  && optionalEqual(left.context_source, right.context_source)
  && left.context_version === right.context_version
  && optionalEqual(left.previous_phase, right.previous_phase)
  && optionalEqual(left.next_phase, right.next_phase)
  && optionalEqual(left.trigger, right.trigger)
  && optionalEqual(left.timestamp, right.timestamp)
  && optionalEqual(left.old_status, right.old_status)
  && optionalEqual(left.new_status, right.new_status)
  && optionalEqual(left.reason, right.reason)
  && optionalEqual(left.step, right.step)
  && optionalEqual(left.error_summary, right.error_summary)
  && optionalEqual(left.source_check_id, right.source_check_id)
  && optionalEqual(left.mismatch_id, right.mismatch_id)
  && optionalEqual(left.mismatch_category, right.mismatch_category)
  && optionalEqual(left.action_type, right.action_type)
  && optionalEqual(left.before_verification_overall, right.before_verification_overall)
  && optionalEqual(left.after_verification_overall, right.after_verification_overall)
  && optionalEqual(left.result, right.result)
  && optionalEqual(left.compact_summary, right.compact_summary)
  && artifactsEqual(left.artifact, right.artifact)
  && JSON.stringify(left.summary ?? null) === JSON.stringify(right.summary ?? null)
  && JSON.stringify(left.blocker ?? null) === JSON.stringify(right.blocker ?? null)
  && left.revision === right.revision
);

const mergeTimelineEvents = (
  previousEvents: RunTimelineEvent[],
  incomingEvents: RunTimelineEvent[]
): RunTimelineEvent[] => {
  if (previousEvents.length === 0) {
    return incomingEvents;
  }
  if (incomingEvents.length < previousEvents.length) {
    return incomingEvents;
  }

  const prefixMatches = previousEvents.every((event, index) => areEventsEqual(event, incomingEvents[index]));
  if (!prefixMatches) {
    return incomingEvents;
  }

  return [...previousEvents, ...incomingEvents.slice(previousEvents.length)];
};

const mergeRunSnapshot = (
  previousSnapshot: RunSnapshot | null,
  incomingRun: RunSnapshot
): RunSnapshot => {
  if (previousSnapshot === null) {
    return incomingRun;
  }

  return {
    ...incomingRun,
    context_events: mergeTimelineEvents(previousSnapshot.context_events, incomingRun.context_events),
  };
};

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
  const [isApplyingCorrection, setIsApplyingCorrection] = useState<boolean>(false);
  const [isResettingEnvironment, setIsResettingEnvironment] = useState<boolean>(false);

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
      setLatestRun((previous) => mergeRunSnapshot(previous, newRun));
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
      setLatestRun((previous) => mergeRunSnapshot(previous, updatedRun));
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

  const handleApplyCorrection = async () => {
    if (isApplyingCorrection || runId === null || !latestRun?.current_phase_proposal) {
      return;
    }
    const proposal = latestRun.current_phase_proposal as Record<string, unknown>;
    const revision = proposal.revision;
    const phase = String(proposal.phase ?? '');
    if (typeof revision !== 'number' || !phase) {
      setError('Correction apply is unavailable for the current proposal.');
      return;
    }
    if (!window.confirm('Apply proposed correction and re-run verification?')) {
      return;
    }
    try {
      setIsApplyingCorrection(true);
      setError('');
      const applyResult = await applyPhaseCorrection(runId, phase, { proposal_revision: revision });
      try {
        const refreshedRun = await fetchRun(runId);
        setLatestRun((previous) => mergeRunSnapshot(previous, refreshedRun));
      } catch (refreshErr) {
        console.error(refreshErr);
        setMessage(
          `Correction ${applyResult.status} for ${phase} revision ${revision}, but run refresh failed. Please reload run details.`
        );
        return;
      }
      setMessage(`Correction ${applyResult.status} for ${phase} revision ${revision}; verification refreshed.`);
    } catch (err) {
      setError('Failed to apply correction. Please try again.');
      console.error(err);
    } finally {
      setIsApplyingCorrection(false);
    }
  };

  const handleResetEnvironment = async () => {
    if (isResettingEnvironment || isSubmitting) {
      return;
    }
    if (
      !window.confirm(
        'Reset the run environment? This permanently deletes all persisted runs for this deployment and cannot be undone.'
      )
    ) {
      return;
    }
    try {
      setIsResettingEnvironment(true);
      setError('');
      await resetRunEnvironment();
      setApiSpec('');
      setMessage('');
      setClarificationQuestions([]);
      setClarificationAnswers({});
      setIsAwaitingClarification(false);
      setRunId(null);
      setLatestRun(null);
      setMessage('Run environment reset. You can start a fresh demo.');
    } catch (err) {
      setError('Failed to reset run environment. Please try again.');
      console.error(err);
    } finally {
      setIsResettingEnvironment(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxWidth: '500px', margin: '20px auto' }}>
      <h2>Initiate New BMAD Run</h2>
      <section
        aria-label="Run administration"
        style={{
          border: '1px solid #e0e0e0',
          borderRadius: '4px',
          padding: '10px',
          backgroundColor: '#fafafa',
        }}
      >
        <p style={{ marginTop: 0, marginBottom: 8, fontWeight: 600 }}>Run administration</p>
        <p style={{ marginTop: 0, marginBottom: 8, fontSize: 13, color: '#555' }}>
          Clear all persisted run data on the server and return this page to an input-ready state for a new demo.
        </p>
        <button
          type="button"
          onClick={handleResetEnvironment}
          disabled={isResettingEnvironment || isSubmitting}
          style={{
            padding: '8px 12px',
            backgroundColor: '#c9302c',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: isResettingEnvironment || isSubmitting ? 'not-allowed' : 'pointer',
            opacity: isResettingEnvironment || isSubmitting ? 0.7 : 1,
          }}
        >
          {isResettingEnvironment ? 'Resetting…' : 'Reset environment'}
        </button>
      </section>
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
          {latestRun.current_phase_proposal && typeof latestRun.current_phase_proposal === 'object'
            && latestRun.current_phase_proposal.verification
            && typeof latestRun.current_phase_proposal.verification === 'object' && (
            <div
              style={{
                marginTop: 10,
                marginBottom: 10,
                padding: '8px 10px',
                border: '1px solid #bce8f1',
                borderRadius: '4px',
                backgroundColor: '#f0f9fc',
              }}
            >
              <p style={{ marginTop: 0, marginBottom: 6 }}>
                <strong>Verification</strong>
                {' '}
                <span
                  style={{
                    padding: '2px 6px',
                    borderRadius: 3,
                    fontSize: 12,
                    fontWeight: 600,
                    background:
                      String((latestRun.current_phase_proposal.verification as Record<string, unknown>).overall) === 'passed'
                        ? '#dff0d8'
                        : '#f2dede',
                    color:
                      String((latestRun.current_phase_proposal.verification as Record<string, unknown>).overall) === 'passed'
                        ? '#3c763d'
                        : '#a94442',
                  }}
                >
                  {String((latestRun.current_phase_proposal.verification as Record<string, unknown>).overall ?? '—')}
                </span>
              </p>
              <details>
                <summary style={{ cursor: 'pointer', fontSize: 13 }}>Checks</summary>
                <ul style={{ marginBottom: 0, paddingLeft: 18, fontSize: 13 }}>
                  {Array.isArray((latestRun.current_phase_proposal.verification as Record<string, unknown>).checks)
                    ? ((latestRun.current_phase_proposal.verification as Record<string, { id?: string; passed?: boolean; message?: string }>).checks).map((c, idx) => (
                      <li key={`${c.id ?? idx}-${idx}`} style={{ marginBottom: 4 }}>
                        <span style={{ fontWeight: 600 }}>{c.id ?? 'check'}</span>
                        {': '}
                        {c.passed ? 'pass' : 'fail'}
                        {c.message ? ` — ${c.message}` : ''}
                      </li>
                    ))
                    : null}
                </ul>
              </details>
              {latestRun.current_phase_proposal.correction_proposal
                && typeof latestRun.current_phase_proposal.correction_proposal === 'object' && (
                <details style={{ marginTop: 8 }}>
                  <summary style={{ cursor: 'pointer', fontSize: 13 }}>Correction proposal</summary>
                  <ul style={{ marginBottom: 0, paddingLeft: 18, fontSize: 13 }}>
                    <li>
                      <strong>Mismatch:</strong>{' '}
                      {String(
                        (latestRun.current_phase_proposal.correction_proposal as Record<string, unknown>)
                          .mismatch_id ?? '—'
                      )}
                    </li>
                    <li>
                      <strong>Target:</strong>{' '}
                      {String(
                        (latestRun.current_phase_proposal.correction_proposal as Record<string, unknown>)
                          .recommended_change_target ?? '—'
                      )}
                    </li>
                    <li>
                      <strong>Guidance:</strong>{' '}
                      {String(
                        (latestRun.current_phase_proposal.correction_proposal as Record<string, unknown>)
                          .patch_guidance ?? '—'
                      )}
                    </li>
                  </ul>
                  <button
                    type="button"
                    onClick={handleApplyCorrection}
                    disabled={isSubmitting || isApplyingCorrection}
                    style={{
                      marginTop: 8,
                      padding: '8px 10px',
                      backgroundColor: '#8a6d3b',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: isApplyingCorrection ? 'not-allowed' : 'pointer',
                      opacity: isApplyingCorrection ? 0.7 : 1,
                    }}
                  >
                    {isApplyingCorrection ? 'Applying correction...' : 'Apply correction'}
                  </button>
                </details>
              )}
            </div>
          )}
          {latestRun.verification_review && (
            <div
              style={{
                marginTop: 10,
                marginBottom: 10,
                padding: '8px 10px',
                border: '1px solid #d6e9c6',
                borderRadius: '4px',
                backgroundColor: '#fcfdf6',
              }}
            >
              <p style={{ marginTop: 0, marginBottom: 6 }}>
                <strong>Verification review</strong>
                {' '}
                <span
                  style={{
                    padding: '2px 6px',
                    borderRadius: 3,
                    fontSize: 12,
                    fontWeight: 600,
                    background:
                      latestRun.verification_review.status === 'blocked'
                        ? '#f2dede'
                        : latestRun.verification_review.verification.overall === 'passed'
                        ? '#dff0d8'
                        : '#fcf8e3',
                    color:
                      latestRun.verification_review.status === 'blocked'
                        ? '#a94442'
                        : latestRun.verification_review.verification.overall === 'passed'
                        ? '#3c763d'
                        : '#8a6d3b',
                  }}
                >
                  {latestRun.verification_review.status}
                </span>
              </p>
              <p style={{ marginTop: 0, marginBottom: 4, fontSize: 13 }}>
                <strong>Mismatch summary:</strong>
                {' '}
                {latestRun.verification_review.verification.fail_count}
                {' '}failed /{' '}
                {latestRun.verification_review.verification.pass_count}
                {' '}passed
              </p>
              <p style={{ marginTop: 0, marginBottom: 4, fontSize: 13 }}>
                <strong>Correction outcome:</strong>
                {' '}
                {latestRun.verification_review.correction.state}
              </p>
              {latestRun.verification_review.blocker ? (
                <p style={{ marginTop: 0, marginBottom: 4, color: '#a94442', fontSize: 13 }}>
                  <strong>Blocker:</strong> {latestRun.verification_review.blocker.message || 'Progression is currently blocked.'}
                </p>
              ) : null}
              <p style={{ marginTop: 0, marginBottom: 0, fontSize: 13 }}>
                <strong>Required next action:</strong> {latestRun.verification_review.required_next_action}
              </p>
            </div>
          )}
          {latestRun.run_complete
            && latestRun.final_output_review
            && latestRun.final_output_review.verification_overview.blocked === false && (
            <div
              role="status"
              aria-live="polite"
              aria-label="Run complete"
              style={{
                marginTop: 10,
                marginBottom: 8,
                padding: '10px 12px',
                border: '2px solid #2e7d32',
                borderRadius: 6,
                backgroundColor: '#e8f5e9',
                color: '#1b5e20',
              }}
            >
              <strong>Run complete</strong>
              <span style={{ display: 'block', marginTop: 6, fontSize: 13, fontWeight: 400 }}>
                All BMAD phases finished and verification shows no unresolved blockers. Final output review
                and local run hints follow below.
              </span>
            </div>
          )}
          {latestRun.final_output_review && (
            <div
              style={{
                marginTop: 10,
                marginBottom: 10,
                padding: '8px 10px',
                border: '1px solid #cfd8dc',
                borderRadius: '4px',
                backgroundColor: '#f7fbff',
              }}
            >
              <p style={{ marginTop: 0, marginBottom: 6 }}>
                <strong>Final output review</strong>
                {' '}
                <span
                  style={{
                    padding: '2px 6px',
                    borderRadius: 3,
                    fontSize: 12,
                    fontWeight: 600,
                    background: latestRun.final_output_review.verification_overview.blocked ? '#f2dede' : '#dff0d8',
                    color: latestRun.final_output_review.verification_overview.blocked ? '#a94442' : '#3c763d',
                  }}
                >
                  {latestRun.final_output_review.verification_overview.blocked ? 'blocked' : 'ready'}
                </span>
              </p>
              <p style={{ marginTop: 0, marginBottom: 4, fontSize: 13 }}>
                <strong>Summary:</strong> {latestRun.final_output_review.artifact_summary.summary || 'No summary available.'}
              </p>
              <p style={{ marginTop: 0, marginBottom: 4, fontSize: 13 }}>
                <strong>Generated files:</strong> {latestRun.final_output_review.artifact_summary.total_files}
                {' '}(
                {latestRun.final_output_review.artifact_summary.backend_files.length} backend /{' '}
                {latestRun.final_output_review.artifact_summary.frontend_files.length} frontend)
              </p>
              <p style={{ marginTop: 0, marginBottom: 4, fontSize: 13 }}>
                <strong>Run locally:</strong> <code>{latestRun.final_output_review.review_access.backend_command}</code>
                {' '}then <code>{latestRun.final_output_review.review_access.frontend_command}</code>
              </p>
              <p style={{ marginTop: 0, marginBottom: 4, fontSize: 13 }}>
                <strong>Open:</strong> {latestRun.final_output_review.review_access.frontend_url}
              </p>
              {latestRun.final_output_review.verification_overview.blocker?.message ? (
                <p style={{ marginTop: 0, marginBottom: 0, color: '#a94442', fontSize: 13 }}>
                  <strong>Verification blocker:</strong> {latestRun.final_output_review.verification_overview.blocker.message}
                </p>
              ) : null}
            </div>
          )}
          <RunTimeline events={latestRun.context_events} />
        </section>
      )}
    </form>
  );
};

export default RunInitiationForm;
