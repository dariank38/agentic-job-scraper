import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import api from '@/services/api';
import type { Developer } from '@/services/api';

const DeveloperDetail = () => {
  const { id } = useParams<{ id: string }>();
  const [developer, setDeveloper] = useState<Developer | null>(null);
  const [status, setStatus] = useState<{ message: string; isError: boolean } | null>(null);
  const [loadingActions, setLoadingActions] = useState<Set<string>>(new Set());
  const [reviewForm, setReviewForm] = useState({ is_approved: 'true', notes: '' });

  useEffect(() => {
    if (id) loadDeveloper(id);
  }, [id]);

  const loadDeveloper = async (devId: string) => {
    try {
      const data = await api.getDeveloper(parseInt(devId));
      setDeveloper(data.developer);
      setReviewForm({
        is_approved: data.developer.is_approved ? 'true' : 'false',
        notes: data.developer.notes || '',
      });
    } catch (error) {
      console.error('Failed to load developer:', error);
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

  const toggleContacted = async () => {
    if (!developer) return;
    try {
      await withLoading('toggle-contacted', () => api.toggleDeveloperContacted(developer.id));
      loadDeveloper(developer.id.toString());
    } catch (error) {
      console.error('Failed to toggle contacted status:', error);
    }
  };

  const submitReview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!developer) return;
    const formData = new FormData();
    formData.append('is_approved', reviewForm.is_approved);
    formData.append('notes', reviewForm.notes);

    try {
      await withLoading('submit-review', () => api.reviewDeveloper(developer.id, formData));
      showStatus('Review saved!');
      setTimeout(() => loadDeveloper(developer.id.toString()), 1000);
    } catch (e: any) {
      showStatus('Error: ' + e.message, true);
    }
  };

  if (!developer) return <p className="p-8 text-gray-500">Loading...</p>;

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
              <h1 className="text-xl font-bold text-gray-900 mb-2">{developer.name || 'Unnamed Developer'}</h1>
              <div className="flex flex-wrap gap-1.5">
                <Badge variant="secondary">Developer</Badge>
                {developer.confidence && <Badge variant="secondary">{developer.confidence}</Badge>}
                <Badge variant={developer.looking_for_work ? 'default' : 'secondary'}>
                  {developer.looking_for_work ? 'Looking for Work' : 'Not Looking'}
                </Badge>
                {developer.is_contacted && <Badge className="bg-green-100 text-green-700 hover:bg-green-100">Contacted</Badge>}
                {!developer.is_reviewed && <Badge variant="outline" className="border-yellow-300 text-yellow-700">Needs Review</Badge>}
                {developer.is_reviewed && developer.is_approved && <Badge className="bg-green-100 text-green-700 hover:bg-green-100">Approved</Badge>}
                {developer.is_reviewed && !developer.is_approved && <Badge variant="secondary">Rejected</Badge>}
              </div>
            </div>
            <div className="flex gap-2 flex-shrink-0">
              <Button
                variant={developer.is_contacted ? 'default' : 'outline'}
                onClick={toggleContacted}
                disabled={loadingActions.has('toggle-contacted')}
              >
                {developer.is_contacted ? 'Contacted ✓' : 'Mark Contacted'}
              </Button>
              <Button asChild variant="outline">
                <Link to="/developers">Back</Link>
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="flex gap-6 flex-col lg:flex-row">
        {/* Main content */}
        <div className="flex-[2] space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Developer Details</CardTitle></CardHeader>
            <CardContent>
              {developer.skills && (() => {
                try {
                  const skills = JSON.parse(developer.skills) as string[];
                  return skills.length > 0 && (
                    <div className="mb-4">
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
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6">
                <DetailRow label="Experience" value={developer.experience} />
                <DetailRow label="GitHub" value={developer.github ? <a href={developer.github} target="_blank" rel="noopener noreferrer" className="text-blue-600">{developer.github}</a> : undefined} />
                <DetailRow label="LinkedIn" value={developer.linkedin ? <a href={developer.linkedin} target="_blank" rel="noopener noreferrer" className="text-blue-600">{developer.linkedin}</a> : undefined} />
                <DetailRow label="Portfolio" value={developer.portfolio ? <a href={developer.portfolio} target="_blank" rel="noopener noreferrer" className="text-blue-600">{developer.portfolio}</a> : undefined} />
                <DetailRow label="Contact" value={developer.contact} />
                <DetailRow label="Contact Type" value={developer.contact_type} />
                <DetailRow label="Source" value={`@${developer.channel?.username || 'Unknown'}`} />
                {developer.message?.sender_username && <DetailRow label="Sender" value={`@${developer.message.sender_username}${developer.message.sender_first_name ? ` (${developer.message.sender_first_name})` : ''}`} />}
                <DetailRow label="Posted" value={developer.message.date ? new Date(developer.message.date).toLocaleString() : 'Unknown'} />
                <DetailRow label="Analyzed" value={developer.analyzed_at ? new Date(developer.analyzed_at).toLocaleString() : 'Unknown'} />
              </div>
            </CardContent>
          </Card>

          {developer.summary && (
            <Card>
              <CardHeader><CardTitle className="text-base">Summary</CardTitle></CardHeader>
              <CardContent><p className="text-sm leading-relaxed">{developer.summary}</p></CardContent>
            </Card>
          )}

          {developer.translated_text && (
            <Card>
              <CardHeader><CardTitle className="text-base">English Translation</CardTitle></CardHeader>
              <CardContent>
                <div className="p-4 bg-gray-50 border-l-4 border-blue-400 rounded-r-lg">
                  <p className="text-sm leading-relaxed m-0">{developer.translated_text}</p>
                </div>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader><CardTitle className="text-base">Original Message</CardTitle></CardHeader>
            <CardContent>
              <pre className="p-4 bg-gray-100 rounded-lg whitespace-pre-wrap font-mono text-sm text-gray-700 max-h-[300px] overflow-y-auto">
                {developer.message.text || 'No text content'}
              </pre>
              {developer.message.has_image && (
                <p className="mt-2 text-orange-500 italic text-sm">This message contains an image</p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="flex-1 space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Review Developer</CardTitle></CardHeader>
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
                <Link to="/developers">All Developers</Link>
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

export default DeveloperDetail;
