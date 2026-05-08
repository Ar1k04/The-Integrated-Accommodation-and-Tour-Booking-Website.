import { Link } from 'react-router-dom'
import { Briefcase } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export default function Footer() {
  const { t } = useTranslation('common')

  const footerLinks = {
    [t('footer.company')]: [
      { label: t('footer.aboutUs'), to: '#' },
      { label: t('footer.careers'), to: '#' },
      { label: t('footer.press'), to: '#' },
      { label: t('footer.blog'), to: '#' },
    ],
    [t('footer.support')]: [
      { label: t('footer.helpCenter'), to: '#' },
      { label: t('footer.safety'), to: '#' },
      { label: t('footer.cancellation'), to: '#' },
      { label: t('footer.contactUs'), to: '#' },
    ],
    [t('footer.explore')]: [
      { label: t('footer.hotels'), to: '/hotels/search' },
      { label: t('footer.tours'), to: '/tours' },
      { label: t('footer.destinations'), to: '#' },
      { label: t('footer.deals'), to: '#' },
    ],
  }

  return (
    <footer className="bg-gray-900 text-gray-300">
      <div className="max-w-7xl mx-auto px-4 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          <div>
            <Link to="/" className="flex items-center gap-2 text-white font-heading text-lg font-bold mb-4">
              <Briefcase className="w-5 h-5" />
              TravelBooking
            </Link>
            <p className="text-sm text-gray-400 leading-relaxed">
              {t('footer.tagline')}
            </p>
          </div>

          {Object.entries(footerLinks).map(([title, links]) => (
            <div key={title}>
              <h3 className="text-white font-semibold mb-4">{title}</h3>
              <ul className="space-y-2">
                {links.map((link) => (
                  <li key={link.label}>
                    <Link to={link.to} className="text-sm hover:text-white transition-colors">
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <hr className="border-gray-700 my-8" />
        <div className="flex flex-col md:flex-row justify-between items-center gap-4 text-sm text-gray-500">
          <p>&copy; {new Date().getFullYear()} TravelBooking. {t('footer.allRightsReserved')}</p>
          <div className="flex gap-6">
            <a href="#" className="hover:text-white">{t('footer.privacyPolicy')}</a>
            <a href="#" className="hover:text-white">{t('footer.termsOfService')}</a>
            <a href="#" className="hover:text-white">{t('footer.cookiePolicy')}</a>
          </div>
        </div>
      </div>
    </footer>
  )
}
