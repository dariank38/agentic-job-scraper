import { useTranslation } from 'react-i18next';
import { Zap, ExternalLink } from 'lucide-react';
import { Separator } from '@/components/ui/separator';

const Footer = () => {
  const { t } = useTranslation();
  return (
    <footer className="bg-background mt-4">
      <Separator />
      <div className="max-w-[1280px] mx-auto px-4 md:px-6 lg:px-8 py-5">
        <div className="flex flex-col md:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <div className="bg-primary/10 text-primary w-5 h-5 rounded flex items-center justify-center">
              <Zap size={11} strokeWidth={2.5} />
            </div>
            <span className="font-medium text-foreground">Job Scraper</span>
            <span className="hidden sm:inline text-muted-foreground/50">·</span>
            <span className="hidden sm:inline">{t('footer.copyright')}</span>
          </div>
          <a
            href="https://github.com"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ExternalLink size={13} />
            {t('footer.github')}
          </a>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
