import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import api from '@/services/api';
import type { Job } from '@/services/api';

const JobDetail = () => {
  const { id } = useParams<{ id: string }>();
  const [job, setJob] = useState<Job | null>(null);
  const [status, setStatus] = useState<{ message: string; isError: boolean } | null>(null);
  const [loadingActions, setLoadingActions] = useState<Set<string>>(new Set());
  const [reviewForm, setReviewForm] = useState({ is_approved: 'true', notes: '' });

  useEffect(() => {
    if (id) loadJob(id);
  }, [id]);

  const loadJob = async (jobId: string) => {
    try {
      const data = await api.getJob(parseInt(jobId));
      setJob(data.job);
      setReviewForm({
        is_approved: data.job.is_approved ? 'true' : 'false',
        notes: data.job.notes || '',
      });
    } catch (error) {
      console.error('Failed to load job:', error);
    }
  };

  const showStatus = (message: string, isError = false) => {
    setStatus({ message, isError });
    setTimeout(() => setStatus(null), 3000);
  };

  const withLoading = async <T,>(
    actionKey: string,
    fn: () => Promise<T>
  ): Promise<T> => {
    setLoadingActions(prev => new Set(prev).add(actionKey));
    try {
      return await fn();
    } finally {
      setLoadingActions(prev => {
        const next = new Set(prev);
        next.delete(actionKey);
        return next;
      });
    }
  };

  const toggleApplied = async () => {
    if (!job) return;
    try {
      await withLoading('toggle-applied', () => api.toggleJobApplied(job.id));
      loadJob(job.id.toString());
    } catch (error) {
      console.error('Failed to toggle applied status:', error);
    }
  };

  const submitReview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!job) return;
    const formData = new FormData();
    formData.append('is_approved', reviewForm.is_approved);
    formData.append('notes', reviewForm.notes);

    try {
      await withLoading('submit-review', () => api.reviewJob(job.id, formData));
      showStatus('Review saved!');
      setTimeout(() => loadJob(job.id.toString()), 1000);
    } catch (e: any) {
      showStatus('Error: ' + e.message, true);
    }
  };

  if (!job) return <p className="p-8 text-gray-500">Loading...</p>;

  const DetailRow = ({ label, value }: { label: string; value?: React.ReactNode }) =>
    value ? (
      <div className="mb-3">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-0.5">{label}</p>
        <div className="text-sm text-gray-800">{value}</div>
      </div>
    ) : null;

  return (
    <>
      {/* Header */}
      <Card className="mb-4">
        <CardContent className="pt-5">
          <div className="flex justify-between items-start gap-4">
            <div>
              <h1 className="text-xl font-bold text-gray-900 mb-2">{job.title || 'Untitled Job'}</h1>
              <div className="flex flex-wrap gap-1.5">
                <Badge variant="secondary">Job Posting</Badge>
                {job.confidence && <Badge variant="secondary">{job.confidence}</Badge>}
                {job.is_applied && <Badge className="bg-green-100 text-green-700 hover:bg-green-100">Applied</Badge>}
                {job.is_remote && <Badge className="bg-teal-100 text-teal-700 hover:bg-teal-100">Remote</Badge>}
                {!job.is_reviewed && <Badge variant="outline" className="border-yellow-300 text-yellow-700">Needs Review</Badge>}
                {job.is_reviewed && job.is_approved && <Badge className="bg-green-100 text-green-700 hover:bg-green-100">Approved</Badge>}
                {job.is_reviewed && !job.is_approved && <Badge variant="secondary">Rejected</Badge>}
              </div>
            </div>
            <div className="flex gap-2 flex-shrink-0">
              <Button
                variant={job.is_applied ? 'default' : 'outline'}
                onClick={toggleApplied}
                disabled={loadingActions.has('toggle-applied')}
              >
                {job.is_applied ? 'Applied ✓' : 'Mark Applied'}
              </Button>
              <Button asChild variant="outline">
                <Link to="/jobs">Back</Link>
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="flex gap-6 flex-col lg:flex-row">
        {/* Main content */}
        <div className="flex-[2] space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Job Details</CardTitle></CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6">
                <DetailRow label="Company" value={job.company} />
                <DetailRow label="Company Link" value={job.company_link ? <a href={job.company_link} target="_blank" rel="noopener noreferrer" className="text-blue-600">{job.company_link}</a> : undefined} />
                <DetailRow label="Location" value={job.location} />
                <DetailRow label="Remote" value={job.is_remote === true ? 'Yes' : job.is_remote === false ? 'No' : 'Unknown'} />
                <DetailRow label="Role Type" value={job.role_type} />
                <DetailRow label="Contact" value={job.contact} />
                <DetailRow label="Contact Type" value={job.contact_type} />
                <DetailRow label="Source" value={`@${job.channel?.username || 'Unknown'}`} />
                {job.message?.sender_username && <DetailRow label="Sender" value={`@${job.message.sender_username}${job.message.sender_first_name ? ` (${job.message.sender_first_name})` : ''}`} />}
                <DetailRow label="Posted" value={job.message.date ? new Date(job.message.date).toLocaleString() : 'Unknown'} />
                <DetailRow label="Analyzed" value={job.analyzed_at ? new Date(job.analyzed_at).toLocaleString() : 'Unknown'} />
              </div>
              {job.skills && (() => {
                try {
                  const skills = JSON.parse(job.skills) as string[];
                  return skills.length > 0 && (
                    <div className="mt-2">
                      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1.5">Skills</p>
                      <div className="flex flex-wrap gap-1">
                        {skills.map((skill, idx) => (
                          <Badge key={idx} variant="secondary" className="rounded-full text-xs">{skill}</Badge>
                        ))}
                      </div>
                    </div>
                  );
                } catch {
                  return null;
                }
              })()}
            </CardContent>
          </Card>

          {job.summary && (
            <Card>
              <CardHeader><CardTitle className="text-base">Summary</CardTitle></CardHeader>
              <CardContent><p className="text-sm leading-relaxed">{job.summary}</p></CardContent>
            </Card>
          )}

          {job.translated_text && (
            <Card>
              <CardHeader><CardTitle className="text-base">English Translation</CardTitle></CardHeader>
              <CardContent>
                <div className="p-4 bg-gray-50 border-l-4 border-blue-400 rounded-r-lg">
                  <p className="text-sm leading-relaxed m-0">{job.translated_text}</p>
                </div>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader><CardTitle className="text-base">Original Message</CardTitle></CardHeader>
            <CardContent>
              <pre className="p-4 bg-gray-100 rounded-lg whitespace-pre-wrap font-mono text-sm text-gray-700 max-h-[300px] overflow-y-auto">
                {job.message.text || 'No text content'}
              </pre>
              {job.message.has_image && (
                <p className="mt-2 text-orange-500 italic text-sm">This message contains an image</p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="flex-1 space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Review Job</CardTitle></CardHeader>
            <CardContent>
              <form onSubmit={submitReview} className="space-y-3">
                <div>
                  <label className="block text-sm font-medium mb-1">Status</label>
                  <select
                    value={reviewForm.is_approved}
                    onChange={(e) => setReviewForm({ ...reviewForm, is_approved: e.target.value })}
                    className="w-full px-3 py-2 rounded-md border border-gray-200 text-sm bg-white"
                  >
                    <option value="true">Approve</option>
                    <option value="false">Reject</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Notes</label>
                  <Textarea
                    value={reviewForm.notes}
                    onChange={(e) => setReviewForm({ ...reviewForm, notes: e.target.value })}
                    placeholder="Add your notes here..."
                    rows={4}
                  />
                </div>
                <Button type="submit" disabled={loadingActions.has('submit-review')} className="w-full">
                  {loadingActions.has('submit-review') ? 'Saving...' : 'Save Review'}
                </Button>
              </form>
              {status && (
                <div className={`mt-3 p-3 rounded-md text-sm ${status.isError ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-green-50 text-green-700 border border-green-200'}`}>
                  {status.message}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-base">Quick Actions</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              <Button asChild variant="outline" className="w-full">
                <Link to="/jobs">All Jobs</Link>
              </Button>
              <Button asChild variant="outline" className="w-full">
                <Link to="/channels">Manage Channels</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
};

export default JobDetail;
