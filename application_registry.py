APPLICATION_SIGNATURES = {
    "googlemeet": {
        "aliases": [
            "google meet",
            "meet",
            "gmeet",
            "google me",
            "google mee"
        ],
        "protocols": ["udp", "tcp"],
        "ports": [443, 3478, 3479, 19302, 19305],
        "dns_patterns": [
            "dns:*.meet.google.com",
            "dns:*.googleapis.com",
            "dns:*.gstatic.com"
        ],
        "priority_class": "video",
        "default_priority": "high",
        "description": "Approximate Google Meet signature for prioritization."
    },

    "zoom": {
        "aliases": [
            "zoom",
            "zoom meeting",
            "zoom meetings"
        ],
        "protocols": ["udp", "tcp"],
        "ports": [443, 3478, 3479, 8801, 8802],
        "dns_patterns": [
            "dns:*.zoom.us",
            "dns:*.zoom.com",
            "dns:*.zoomgov.com"
        ],
        "priority_class": "video",
        "default_priority": "high",
        "description": "Approximate Zoom signature for meetings and media flows."
    },

    "microsoftteams": {
        "aliases": [
            "microsoft teams",
            "teams",
            "ms teams",
            "msteams"
        ],
        "protocols": ["udp", "tcp"],
        "ports": [80, 443, 3478, 3479, 3480, 3481],
        "dns_patterns": [
            "dns:*.teams.microsoft.com",
            "dns:*.skype.com",
            "dns:*.lync.com",
            "dns:*.office.com",
            "dns:*.office365.com"
        ],
        "priority_class": "video",
        "default_priority": "high",
        "description": "Approximate Microsoft Teams signature for calling and meetings."
    },

    "discord": {
        "aliases": [
            "discord",
            "discord call",
            "discord voice"
        ],
        "protocols": ["udp", "tcp"],
        "ports": [80, 443, 3478, 3479],
        "dns_patterns": [
            "dns:*.discord.com",
            "dns:*.discord.gg",
            "dns:*.discordapp.com",
            "dns:*.discordmedia.com"
        ],
        "priority_class": "video",
        "default_priority": "high",
        "description": "Approximate Discord signature for chat, voice, and media."
    },

    "youtube": {
        "aliases": [
            "youtube",
            "yt",
            "youtube video"
        ],
        "protocols": ["udp", "tcp"],
        "ports": [80, 443],
        "dns_patterns": [
            "dns:*.youtube.com",
            "dns:*.googlevideo.com",
            "dns:*.ytimg.com",
            "dns:*.youtubei.googleapis.com"
        ],
        "priority_class": "video",
        "default_priority": "medium",
        "description": "Approximate YouTube signature for streaming video."
    },

    "netflix": {
        "aliases": [
            "netflix",
            "net flix"
        ],
        "protocols": ["udp", "tcp"],
        "ports": [80, 443],
        "dns_patterns": [
            "dns:*.netflix.com",
            "dns:*.nflxvideo.net",
            "dns:*.nflximg.net",
            "dns:*.nflxext.com",
            "dns:*.nflxso.net"
        ],
        "priority_class": "video",
        "default_priority": "medium",
        "description": "Approximate Netflix signature for streaming playback."
    },

    "twitch": {
        "aliases": [
            "twitch",
            "twitch tv",
            "twitch stream"
        ],
        "protocols": ["udp", "tcp"],
        "ports": [80, 443],
        "dns_patterns": [
            "dns:*.twitch.tv",
            "dns:*.ttvnw.net",
            "dns:*.jtvnw.net"
        ],
        "priority_class": "video",
        "default_priority": "medium",
        "description": "Approximate Twitch signature for live streaming."
    },

    "steam": {
        "aliases": [
            "steam",
            "steam games",
            "valve steam"
        ],
        "protocols": ["udp", "tcp"],
        "ports": [80, 443, 27015, 27031, 27036],
        "dns_patterns": [
            "dns:*.steampowered.com",
            "dns:*.steamcontent.com",
            "dns:*.steamstatic.com",
            "dns:*.akamaihd.net"
        ],
        "priority_class": "gaming",
        "default_priority": "high",
        "description": "Approximate Steam signature for downloads, updates, and gaming services."
    },

    "tiktok": {
        "aliases": [
            "tiktok",
            "tik tok"
        ],
        "protocols": ["udp", "tcp"],
        "ports": [80, 443],
        "dns_patterns": [
            "dns:*.tiktok.com",
            "dns:*.tiktokv.com",
            "dns:*.byteoversea.com",
            "dns:*.ibytedtos.com"
        ],
        "priority_class": "video",
        "default_priority": "medium",
        "description": "Approximate TikTok signature for short-form video."
    },

    "whatsapp": {
        "aliases": [
            "whatsapp",
            "whats app",
            "wa"
        ],
        "protocols": ["udp", "tcp"],
        "ports": [80, 443, 3478, 3479, 3480],
        "dns_patterns": [
            "dns:*.whatsapp.net",
            "dns:*.whatsapp.com",
            "dns:*.facebook.com",
            "dns:*.fbcdn.net"
        ],
        "priority_class": "voice",
        "default_priority": "high",
        "description": "Approximate WhatsApp signature for messaging and calling."
    },

    "chatgpt": {
        "aliases": [
            "chatgpt",
            "chat gpt",
            "openai chatgpt",
            "gpt"
        ],
        "protocols": ["tcp"],
        "ports": [80, 443],
        "dns_patterns": [
            "dns:*.openai.com",
            "dns:*.chatgpt.com",
            "dns:*.oaistatic.com"
        ],
        "priority_class": "besteffort",
        "default_priority": "medium",
        "description": "Approximate ChatGPT/OpenAI signature for web and app access."
    }
}