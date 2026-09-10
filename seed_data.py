import os
import sys
import django
from datetime import timedelta

# Ensure UTF-8 stdout on Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'election_system.settings')
django.setup()

from django.utils import timezone
from apps.accounts.models import User
from apps.elections.models import Election, Position, Candidate, Ballot, HasVoted
from apps.audit.ledger import log_audit_event, ensure_genesis_block
from apps.audit.models import AuditLog

def populate_seed_data():
    print("Initializing Abubakar Tafawa Balewa University (ATBU) E-Voting Database...")

    # 1. Clear all existing logins, sessions, credentials, and ballots
    from apps.biometrics.models import WebAuthnCredential
    from django.contrib.sessions.models import Session
    
    Session.objects.all().delete()
    WebAuthnCredential.objects.all().delete()
    Ballot.objects.all().delete()
    HasVoted.objects.all().delete()
    User.objects.all().delete()
    Election.objects.all().delete()
    AuditLog.objects.all().delete()
    print("[+] Cleared all previous user logins, credentials, sessions, and ballots.")

    # 2. Initialize Genesis Audit Block
    ensure_genesis_block()
    print("[+] Genesis Block #1 verified.")

    # 3. Create Single UNECO Administrator Login
    admin_user = User.objects.create(
        username="ATBU/ADMIN/001",
        matric_no="ATBU/ADMIN/001",
        first_name="Dr. Mansur",
        last_name="Ahmed",
        email="uneco@atbu.edu.ng",
        role=User.ROLE_ADMIN,
        is_staff=True,
        is_superuser=True,
        faculty="Faculty of Science",
        department="Computer Science",
        level=900,
        is_verified=True
    )
    admin_user.set_password('AdminSecret2026!')
    admin_user.ensure_totp_secret()
    admin_user.save()
    print(f"[+] UNECO Admin: {admin_user.matric_no} (Password: AdminSecret2026!)")

    now = timezone.now()
    
    # =========================================================================
    # ELECTION 1: SUG General Election
    # Positions: President, Vice President, Secretary General, Assistant Secretary General,
    #            Financial Secretary, Director of Socials, Director of Welfare
    # =========================================================================
    sug_election = Election.objects.create(
        title="2025/2026 ATBU Student Union Government (SUG) General Election",
        description="",
        category=Election.CATEGORY_SUG,
        status=Election.STATUS_ACTIVE,
        start_time=now - timedelta(days=1),
        end_time=now + timedelta(days=3),
        created_by=admin_user
    )


    sug_positions_data = [
        {
            'title': 'President',
            'order': 1,
            'candidates': [
                {
                    'name': 'David Obinna Eze',
                    'nickname': 'The Catalyst',
                    'matric': '20/51234U/1',
                    'manifesto': 'Prioritizing 24/7 library electricity, digital transcript automation, and transparent student union budgeting.'
                },
                {
                    'name': 'Abubakar Sadiq Bello',
                    'nickname': 'Voice of Reform',
                    'matric': '20/52345U/1',
                    'manifesto': 'Subsidized campus transit shuttles, student emergency welfare funds, and solar power study hubs.'
                }
            ]
        },
        {
            'title': 'Vice President',
            'order': 2,
            'candidates': [
                {
                    'name': 'Fatima Zahra Aliyu',
                    'nickname': 'Grace & Action',
                    'matric': '21/63456U/1',
                    'manifesto': 'Academic mentorship networks, hostel sanitation overhauls, and women in leadership skills workshops.'
                },
                {
                    'name': 'Blessing Nkechi Adebayo',
                    'nickname': 'Impact Leader',
                    'matric': '21/64567U/1',
                    'manifesto': 'Uniting faculties through inter-departmental innovation competitions and healthcare access.'
                }
            ]
        },
        {
            'title': 'Secretary General',
            'order': 3,
            'candidates': [
                {
                    'name': 'Kelechi Samuel Nwosu',
                    'nickname': 'The Scribe',
                    'matric': '21/65678U/1',
                    'manifesto': 'Digitalizing union meeting minutes, prompt official notices, and transparent record keeping.'
                },
                {
                    'name': 'Usman Farouk Mohammed',
                    'nickname': 'Al-Qalam',
                    'matric': '21/66789U/1',
                    'manifesto': 'Timely student correspondence, open-door administration, and digital student newsletter.'
                }
            ]
        },
        {
            'title': 'Assistant Secretary General',
            'order': 4,
            'candidates': [
                {
                    'name': 'Maryam Kabir Hassan',
                    'nickname': 'Dedicated Scribe',
                    'matric': '22/71234U/1',
                    'manifesto': 'Efficient documentation, supporting senate resolutions, and timely dispatch of union circulars.'
                },
                {
                    'name': 'Joshua Emmanuel Danladi',
                    'nickname': 'JD',
                    'matric': '22/72345U/1',
                    'manifesto': 'Enhancing administrative efficiency and supporting cross-faculty communication channels.'
                }
            ]
        },
        {
            'title': 'Financial Secretary',
            'order': 5,
            'candidates': [
                {
                    'name': 'Ibrahim Musa Sani',
                    'nickname': 'Accountability',
                    'matric': '21/67890U/1',
                    'manifesto': 'Prudent financial management, public expenditure reporting, and budget accountability.'
                },
                {
                    'name': 'Grace Chidimma Okoro',
                    'nickname': 'Integrity',
                    'matric': '21/68901U/1',
                    'manifesto': 'Transparent financial auditing, sponsorship sourcing, and student grant administration.'
                }
            ]
        },
        {
            'title': 'Director of Socials',
            'order': 6,
            'candidates': [
                {
                    'name': 'Tunde Victor Balogun',
                    'nickname': 'DJ Apex',
                    'matric': '21/69012U/1',
                    'manifesto': 'Annual campus cultural carnivals, gaming and esports hackathons, and creative arts festivals.'
                },
                {
                    'name': 'Mustapha Umar Garba',
                    'nickname': 'Vibe Master',
                    'matric': '21/70123U/1',
                    'manifesto': 'Inclusive campus social events, talent discovery showcases, and open-air movie nights.'
                }
            ]
        },
        {
            'title': 'Director of Welfare',
            'order': 7,
            'candidates': [
                {
                    'name': 'Aisha Abdullahi Shehu',
                    'nickname': 'Care Advocate',
                    'matric': '21/71234U/1',
                    'manifesto': 'Improving hostel living conditions, water supply monitoring, and subsidized cafeteria meals.'
                },
                {
                    'name': 'Michael Chukwuemeka Eze',
                    'nickname': 'People First',
                    'matric': '21/72345U/1',
                    'manifesto': 'Health center advocacy, mental wellness support, and student emergency assistance desk.'
                }
            ]
        }
    ]

    for p_info in sug_positions_data:
        pos = Position.objects.create(
            election=sug_election,
            title=p_info['title'],
            order_num=p_info['order'],
            max_choices=1
        )
        for c_info in p_info['candidates']:
            Candidate.objects.create(
                position=pos,
                full_name=c_info['name'],
                nickname=c_info['nickname'],
                matric_no=c_info['matric'],
                manifesto=c_info['manifesto'],
                photo_url='/static/img/default_avatar.svg',
                cgpa_cleared=True,
                status=Candidate.STATUS_APPROVED
            )

    print(f"[+] SUG General Election Initialized with {Position.objects.filter(election=sug_election).count()} executive positions.")

    # =========================================================================
    # ELECTION 2: NACOS (Nigeria Association of Computing Students) Election
    # Positions: President, Vice President, Secretary General, Financial Secretary,
    #            Director of Software & Technical
    # =========================================================================
    nacos_election = Election.objects.create(
        title="2025/2026 Nigeria Association of Computing Students (NACOS) Election",
        description="",
        category=Election.CATEGORY_DEPARTMENTAL,
        faculty="Faculty of Science",
        department="Computer Science",
        status=Election.STATUS_ACTIVE,
        start_time=now - timedelta(hours=12),
        end_time=now + timedelta(days=2),
        created_by=admin_user
    )


    nacos_positions_data = [
        {
            'title': 'NACOS President',
            'order': 1,
            'candidates': [
                {
                    'name': 'Somtochukwu Paul Okafor',
                    'nickname': 'Tech Lead',
                    'matric': '20/54399U/1',
                    'manifesto': 'Organizing annual ATBU hackathons, departmental cloud server access, and industry internships.'
                },
                {
                    'name': 'Aminu Mohammed Kabir',
                    'nickname': 'CodeMaster',
                    'matric': '20/54400U/1',
                    'manifesto': 'Peer-to-peer coding bootcamps, computer lab hardware upgrades, and open source mentorship.'
                }
            ]
        },
        {
            'title': 'NACOS Vice President',
            'order': 2,
            'candidates': [
                {
                    'name': 'Hadiza Sanusi Bello',
                    'nickname': 'Dev Queen',
                    'matric': '21/64411U/1',
                    'manifesto': 'Women-in-tech workshops, academic tutorial circles for junior levels, and departmental tech seminars.'
                },
                {
                    'name': 'Deborah Oluwaseun Davies',
                    'nickname': 'Byte Queen',
                    'matric': '21/64422U/1',
                    'manifesto': 'Student developer partnerships, resume review sessions, and tech community meetups.'
                }
            ]
        },
        {
            'title': 'NACOS Secretary General',
            'order': 3,
            'candidates': [
                {
                    'name': 'Victor Daniel Onyeka',
                    'nickname': 'The Documenter',
                    'matric': '21/64433U/1',
                    'manifesto': 'Building an online departmental repository for lecture notes, past exam questions, and project templates.'
                },
                {
                    'name': 'Haruna Idris Yakubu',
                    'nickname': 'Scribe Tech',
                    'matric': '21/64444U/1',
                    'manifesto': 'Prompt departmental circulars, broadcast channels for internship opportunities, and transparent minutes.'
                }
            ]
        },
        {
            'title': 'NACOS Financial Secretary',
            'order': 4,
            'candidates': [
                {
                    'name': 'Zainab Ahmad Tijani',
                    'nickname': 'Ledger Pro',
                    'matric': '21/64455U/1',
                    'manifesto': 'Transparent departmental dues auditing, corporate sponsorships for tech week, and zero-waste budgeting.'
                },
                {
                    'name': 'Caleb Ikechukwu Nnamdi',
                    'nickname': 'FinTech',
                    'matric': '21/64466U/1',
                    'manifesto': 'Automated dues receipt generation and securing hardware grants for student software projects.'
                }
            ]
        },
        {
            'title': 'Director of Software & Technical',
            'order': 5,
            'candidates': [
                {
                    'name': 'Mahmud Al-Hassan Garba',
                    'nickname': 'Root Access',
                    'matric': '21/64477U/1',
                    'manifesto': 'Hosting weekly algorithms and web development masterclasses, and building ATBU student utility apps.'
                },
                {
                    'name': 'Joy Chiamaka Peters',
                    'nickname': 'Cyber Joy',
                    'matric': '21/64488U/1',
                    'manifesto': 'Cybersecurity CTF training, cloud computing workshops, and modern programming toolsets.'
                }
            ]
        }
    ]

    for p_info in nacos_positions_data:
        pos = Position.objects.create(
            election=nacos_election,
            title=p_info['title'],
            order_num=p_info['order'],
            max_choices=1
        )
        for c_info in p_info['candidates']:
            Candidate.objects.create(
                position=pos,
                full_name=c_info['name'],
                nickname=c_info['nickname'],
                matric_no=c_info['matric'],
                manifesto=c_info['manifesto'],
                photo_url='/static/img/default_avatar.svg',
                cgpa_cleared=True,
                status=Candidate.STATUS_APPROVED
            )

    print(f"[+] NACOS Election Initialized with {Position.objects.filter(election=nacos_election).count()} executive positions.")

    log_audit_event(
        AuditLog.EVENT_ADMIN_ACTION,
        user=admin_user,
        details={"action": "ATBU Election system seeded with SUG and NACOS elections"}
    )

    print("\nDatabase Seed Completed Successfully.")
    print("-" * 55)
    print("Single System Administrator Login:")
    print(f"   UNECO Admin: {admin_user.matric_no}")
    print("   Password:    AdminSecret2026!")
    print("   Role:        System Admin / UNECO Command Center")
    print("-" * 55)
    print("Note: No student voter logins are seeded.")
    print("Students can register independently at /accounts/register/")
    print("and enroll their device fingerprint.")
    print("-" * 55)

if __name__ == '__main__':
    populate_seed_data()
