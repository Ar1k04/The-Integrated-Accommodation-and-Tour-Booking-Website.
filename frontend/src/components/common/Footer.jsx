import { Link } from 'react-router-dom'
import { Briefcase } from 'lucide-react'

const footerLinks = {
  Company: [
    { label: 'About Us', to: '#' },
    { label: 'Careers', to: '#' },
    { label: 'Press', to: '#' },
    { label: 'Blog', to: '#' },
  ],
  Support: [
    { label: 'Help Center', to: '#' },
    { label: 'Safety', to: '#' },
    { label: 'Cancellation', to: '#' },
    { label: 'Contact Us', to: '#' },
  ],
  Explore: [
    { label: 'Hotels', to: '/hotels/search' },
    { label: 'Tours', to: '/tours' },
    { label: 'Destinations', to: '#' },
    { label: 'Deals', to: '#' },
  ],
}

export default function Footer() {
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
              Your trusted companion for finding the best hotels and tours worldwide.
              Best price guaranteed.
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
          <p>&copy; {new Date().getFullYear()} TravelBooking. All rights reserved.</p>
          <div className="flex gap-6">
            <a href="#" className="hover:text-white">Privacy Policy</a>
            <a href="#" className="hover:text-white">Terms of Service</a>
            <a href="#" className="hover:text-white">Cookie Policy</a>
          </div>
        </div>
      </div>
    </footer>
  )
}
