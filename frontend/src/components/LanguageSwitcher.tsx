import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Globe } from 'lucide-react';

export const LanguageSwitcher = () => {
  const { i18n } = useTranslation();

  const toggleLanguage = () => {
    const newLang = i18n.language === 'en' ? 'zh' : 'en';
    i18n.changeLanguage(newLang);
  };

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={toggleLanguage}
      title={i18n.language === 'en' ? '中文' : 'English'}
      className="flex items-center gap-2"
    >
      <Globe className="w-4 h-4" />
      <span className="text-sm hidden xl:inline">
        {i18n.language === 'en' ? '中文' : 'English'}
      </span>
    </Button>
  );
};
