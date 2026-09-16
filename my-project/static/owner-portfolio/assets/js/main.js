const year = document.querySelector('[data-year]');
if (year) year.textContent = new Date().getFullYear();

const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const isFinePointer = window.matchMedia('(pointer: fine)').matches;

function ensureAmbient() {
  const layers = [
    ['scroll-progress', 'div'],
    ['cursor-glow', 'div'],
    ['orbs', 'div'],
    ['particles', 'div'],
  ];

  layers.forEach(([cls, tag]) => {
    if (!document.querySelector('.' + cls)) {
      const el = document.createElement(tag);
      el.className = cls;
      el.setAttribute('aria-hidden', 'true');
      document.body.prepend(el);
    }
  });

  const orbs = document.querySelector('.orbs');
  if (orbs && !orbs.children.length) {
    ['orb-a', 'orb-b', 'orb-c'].forEach((name) => {
      const span = document.createElement('span');
      span.className = 'orb ' + name;
      orbs.appendChild(span);
    });
  }
}

ensureAmbient();

const reveals = document.querySelectorAll('.reveal');
const io = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (!entry.isIntersecting) return;
    const siblings = [...entry.target.parentElement.children].filter((el) =>
      el.classList.contains('reveal')
    );
    const index = Math.max(0, siblings.indexOf(entry.target));
    entry.target.style.transitionDelay = `${Math.min(index * 120, 480)}ms`;
    entry.target.classList.add('show');
    io.unobserve(entry.target);
  });
}, { threshold: 0.12, rootMargin: '0px 0px -12% 0px' });

reveals.forEach((el) => {
  if (el.classList.contains('show') || reduceMotion) {
    el.classList.add('show');
    return;
  }
  io.observe(el);
});

const particlesWrap = document.querySelector('.particles');
if (particlesWrap && !reduceMotion) {
  const count = window.innerWidth < 700 ? 12 : 26;
  for (let i = 0; i < count; i++) {
    const p = document.createElement('span');
    p.className = 'particle';
    const size = Math.random() * 3 + 1.5;
    p.style.width = `${size}px`;
    p.style.height = `${size}px`;
    p.style.left = `${Math.random() * 100}%`;
    p.style.top = `${Math.random() * 100}%`;
    p.style.animationDuration = `${7 + Math.random() * 9}s`;
    p.style.animationDelay = `${Math.random() * 8}s`;
    particlesWrap.appendChild(p);
  }
}

const header = document.querySelector('.site-header');
const progress = document.querySelector('.scroll-progress');

function onScroll() {
  const y = window.scrollY || 0;
  if (header) header.classList.toggle('is-scrolled', y > 12);
  if (progress) {
    const max = document.documentElement.scrollHeight - window.innerHeight;
    const ratio = max > 0 ? y / max : 0;
    progress.style.width = `${Math.min(100, Math.max(0, ratio * 100))}%`;
  }
}

onScroll();
window.addEventListener('scroll', onScroll, { passive: true });

const sections = [...document.querySelectorAll('main section[id]')];
const navLinks = [...document.querySelectorAll('.nav-links a')];

function updateActiveNav() {
  if (!sections.length || !navLinks.length) return;
  if (window.scrollY < 120) {
    navLinks.forEach((link) => link.classList.remove('is-active'));
    return;
  }
  const fromTop = window.scrollY + 120;
  let current = sections[0].id;
  sections.forEach((section) => {
    if (section.offsetTop <= fromTop) current = section.id;
  });
  if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 80) {
    current = sections[sections.length - 1].id;
  }
  navLinks.forEach((link) => {
    const href = link.getAttribute('href') || '';
    link.classList.toggle('is-active', href.endsWith('#' + current));
  });
}

updateActiveNav();
window.addEventListener('scroll', updateActiveNav, { passive: true });

if (isFinePointer && !reduceMotion) {
  window.addEventListener('pointermove', (e) => {
    document.documentElement.style.setProperty('--mx', `${e.clientX}px`);
    document.documentElement.style.setProperty('--my', `${e.clientY}px`);
  }, { passive: true });
}

document.querySelectorAll('.glass.card').forEach((card) => {
  card.classList.add('spotlight-card');
});

document.querySelectorAll('.spotlight-card').forEach((card) => {
  if (!card.querySelector('.spot-glow')) {
    const glow = document.createElement('span');
    glow.className = 'spot-glow';
    glow.setAttribute('aria-hidden', 'true');
    card.appendChild(glow);
  }

  if (!isFinePointer || reduceMotion) return;

  card.addEventListener('pointermove', (e) => {
    const rect = card.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    card.style.setProperty('--spot-x', `${x}%`);
    card.style.setProperty('--spot-y', `${y}%`);
  });
});

const tiltCard = document.querySelector('[data-tilt]');
if (tiltCard && isFinePointer && !reduceMotion) {
  const wrap = tiltCard.closest('.hero-visual-wrap') || tiltCard;
  wrap.addEventListener('pointermove', (e) => {
    const rect = wrap.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;
    tiltCard.style.transform = `rotateY(${x * 12}deg) rotateX(${y * -10}deg) translateY(-6px)`;
  });
  wrap.addEventListener('pointerleave', () => {
    tiltCard.style.transform = 'rotateY(0deg) rotateX(0deg) translateY(0)';
  });
}

document.querySelectorAll('.magnetic').forEach((btn) => {
  if (!isFinePointer || reduceMotion) return;
  btn.addEventListener('pointermove', (e) => {
    const rect = btn.getBoundingClientRect();
    const x = e.clientX - rect.left - rect.width / 2;
    const y = e.clientY - rect.top - rect.height / 2;
    btn.style.transform = `translate(${x * 0.18}px, ${y * 0.22}px)`;
  });
  btn.addEventListener('pointerleave', () => {
    btn.style.transform = '';
  });
});

document.querySelectorAll('.profile-photo-frame img').forEach((img) => {
  const hide = () => img.classList.add('is-hidden');
  img.addEventListener('error', hide);
  if (img.complete && img.naturalWidth === 0) hide();
});

const contactForm = document.querySelector('.contact-form');
if (contactForm) {
  contactForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const button = contactForm.querySelector('button');
    if (!button) return;
    const original = button.textContent;
    button.textContent = '送信しました';
    button.disabled = true;
    setTimeout(() => {
      button.textContent = original;
      button.disabled = false;
      contactForm.reset();
    }, 1800);
  });
}
