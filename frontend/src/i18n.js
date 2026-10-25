/* Languages for people who cannot, or would rather not, type in English.
   One choice drives three things: the words on the page, the language the microphone listens in, and the language the AI answers in.
   The server always gets the English value of each dropdown ("Weak grip or arthritis"); only what people read is translated.
   The words below were written by a machine and need a native speaker's read before the page goes in front of the public. */

const LANGS = [
  { id: 'en', label: 'English', ai: '',        speech: 'en-IN' },
  { id: 'hi', label: 'हिन्दी',   ai: 'Hindi',   speech: 'hi-IN' },
  { id: 'kn', label: 'ಕನ್ನಡ',    ai: 'Kannada', speech: 'kn-IN' },
  { id: 'ta', label: 'தமிழ்',    ai: 'Tamil',   speech: 'ta-IN' },
  { id: 'te', label: 'తెలుగు',   ai: 'Telugu',  speech: 'te-IN' }
];

const T = {
  en: {
    'lang.label': 'Language',
    'idle': 'Printer ready. Describe a part and it starts here.',
    'stage.asking': 'Reading your request', 'stage.queued': 'In the queue', 'stage.planning': 'Reading your request',
    'stage.designing': 'The AI is designing your part. This can take a minute or two.',
    'stage.building': 'Building the files and checking they can be printed', 'stage.working': 'Working',
    's.write': 'The AI is writing the CAD code for your part', 's.fix': 'The AI is fixing the design',
    's.approved': 'The AI checked its own render and approved the design',
    's.check': 'Checking the shape: closed solid, wall thickness, overhangs',
    's.problem': 'Found a problem, sending it back to the AI to fix', 's.render': 'Rendering the part so the AI can look at it',
    'note.empty': 'Tell us what is hard to use first.',
    'note.demo': 'Demo only: nothing was uploaded or sent. In ReForm3D these inputs go to the AI pipeline shown above.',
    'status.demo': 'Demo mode: no design server is connected to this page.',
    'status.ai': 'Design server online. AI design is on ({m}); {t} ready-made parts as a fallback.',
    'status.noai': 'Design server online, AI design is off: requests are matched to {t} ready-made parts.',
    'status.off': 'The design server is not reachable right now. Check the server address, then reload.',
    'models': 'models', 'err.generic': 'Something went wrong. Try again.',
    'q.title': 'A few quick questions', 'q.sub': 'So the part fits. Change any answer that is wrong.', 'q.go': 'Design my part', 'q.skip': 'Skip the questions',
    'done': 'Done. Your part is ready.',
    'res.part': 'Your part', 'res.ai': 'Designed from scratch by the AI', 'res.tpl': 'Ready-made part, sized for you',
    'res.stage': 'Your part is on the stage to the left. Drag to turn it.',
    'res.zip': 'Download everything (.zip)', 'res.fit': 'Fit test', 'res.notes': 'Print notes',
    'res.closed': 'closed solid', 'res.attn': 'needs attention',
    'res.warn': 'Check before you print', 'res.assumed': 'Sizes it assumed. Check these against the real object.', 'res.how': 'How to print it', 'res.fit2': 'Fit',
    'res.disc': 'Test print before relying on it. Printed parts are light-duty aids, not safety equipment.',
    'tune.title': 'Adjust the sizes', 'tune.sub': 'no AI, a few seconds', 'tune.go': 'Rebuild with these sizes',
    'rev.q': 'Want the design changed?', 'rev.ph': 'Make the grip 10 mm longer and round the edges.', 'rev.go': 'Change the design',
    'est.sliced': 'Sliced with {src}: about {g} g of {m}, about {min} min to print.', 'est.rough': 'Rough estimate: about {g} g of {m}, about {min} min to print.',
    'o.cached': 'Made earlier for the same request, so no AI call was needed.', 'o.tuned': 'Rebuilt with your sizes, no AI involved.', 'o.revised': 'Changed as you asked.',
    'how.one': '{n} design pass', 'how.many': '{n} design passes', 'how.reviewed': ', checked against a picture of its own result', 'how.by': '. Designed by {m}',
    'hist.btn': 'History', 'hist.title': 'History & Statistics', 'close': 'Close', 'tab.stats': 'Statistics',
    'hist.loading': 'Loading history…', 'hist.err': 'History could not be loaded. Please try again.',
    'mic.start': 'Speak instead of typing', 'mic.stop': 'Stop listening', 'mic.listening': 'Listening… speak now.',
    'mic.denied': 'The microphone is blocked. Allow it in your browser settings, then try again.',
    'mic.unsupported': 'Speaking is not available in this browser. Try Chrome, Edge or Safari.',
    'mic.nospeech': 'Heard nothing. Try again.', 'mic.network': 'Could not reach the speech service. Check your internet.',
    'mic.nolang': 'This browser cannot listen in this language. Type instead, or pick another language.'
  },
  hi: {
    'nav.problem': 'समस्या', 'nav.how': 'यह कैसे काम करता है', 'nav.examples': 'उदाहरण', 'nav.start': 'वस्तु ढालें',
    'repair.title': 'बताइए क्या इस्तेमाल करना मुश्किल है।',
    'repair.intro': 'कुछ तस्वीरें भेजिए, हम ऐसा पुर्ज़ा डिज़ाइन करेंगे जो इसे इस्तेमाल करना आसान बना दे। AI यही पढ़ता है: 1–3 तस्वीरें, चाहें तो माप, समस्या का विवरण, यह किसके लिए है, और सामग्री की पसंद।',
    'drop.b': '1–3 तस्वीरें छोड़ें', 'drop.rest': ' या चुनने के लिए टैप करें',
    'what.label': 'समस्या क्या है?', 'what.ph': 'मेरी दादी पानी की बोतल का चिकना ढक्कन पकड़ नहीं पातीं।',
    'dims.label': 'माप (वैकल्पिक)', 'dims.ph': 'जैसे गर्दन 50 मिमी',
    'mat.label': 'सामग्री की पसंद', 'mat.0': 'कोई पसंद नहीं', 'mat.1': 'टिकाऊ', 'mat.2': 'लचीला और पकड़ने में आसान',
    'who.label': 'यह किसके लिए है?', 'who.0': 'किसी के भी लिए', 'who.1': 'कमज़ोर पकड़ या गठिया', 'who.2': 'कम दिखना या दृष्टिहीन', 'who.3': 'चलने-फिरने में कठिनाई', 'who.4': 'हाथ काँपना या उँगलियों में कम पकड़',
    'submit': 'पुर्ज़े का अनुरोध करें',
    'step.0': 'पढ़ना', 'step.1': 'डिज़ाइन', 'step.2': 'जाँच', 'step.3': 'फ़ाइलें बनाना',
    'lang.label': 'भाषा',
    'idle': 'प्रिंटर तैयार है। पुर्ज़े का वर्णन करें, यहीं से शुरू होगा।',
    'stage.asking': 'आपका अनुरोध पढ़ा जा रहा है', 'stage.queued': 'कतार में है', 'stage.planning': 'आपका अनुरोध पढ़ा जा रहा है',
    'stage.designing': 'AI आपका पुर्ज़ा डिज़ाइन कर रहा है। इसमें एक-दो मिनट लग सकते हैं।',
    'stage.building': 'फ़ाइलें बन रही हैं और जाँचा जा रहा है कि वे प्रिंट हो सकती हैं', 'stage.working': 'काम चल रहा है',
    's.write': 'AI आपके पुर्ज़े का CAD कोड लिख रहा है', 's.fix': 'AI डिज़ाइन ठीक कर रहा है',
    's.approved': 'AI ने अपने रेंडर को जाँचकर डिज़ाइन मंज़ूर किया',
    's.check': 'आकार की जाँच: ठोस और बंद, दीवार की मोटाई, ओवरहैंग',
    's.problem': 'समस्या मिली, ठीक करने के लिए AI को वापस भेजा जा रहा है', 's.render': 'पुर्ज़े का रेंडर बनाया जा रहा है ताकि AI उसे देख सके',
    'note.empty': 'पहले बताइए कि क्या इस्तेमाल में मुश्किल है।',
    'note.demo': 'सिर्फ़ डेमो: कुछ भी अपलोड या भेजा नहीं गया। ReForm3D में ये जानकारी ऊपर दिखाई गई AI प्रक्रिया में जाती है।',
    'status.demo': 'डेमो मोड: इस पेज से कोई डिज़ाइन सर्वर जुड़ा नहीं है।',
    'status.ai': 'डिज़ाइन सर्वर चालू है। AI डिज़ाइन चालू है ({m}); बैकअप के रूप में {t} बने-बनाए पुर्ज़े हैं।',
    'status.noai': 'डिज़ाइन सर्वर चालू है, AI डिज़ाइन बंद है: अनुरोध {t} बने-बनाए पुर्ज़ों से मिलाए जाएँगे।',
    'status.off': 'डिज़ाइन सर्वर अभी नहीं मिल रहा। सर्वर का पता जाँचें, फिर पेज दोबारा लोड करें।',
    'models': 'मॉडल', 'err.generic': 'कुछ गड़बड़ हो गई। फिर कोशिश करें।',
    'q.title': 'कुछ छोटे सवाल', 'q.sub': 'ताकि पुर्ज़ा ठीक बैठे। कोई उत्तर गलत हो तो बदल दें।', 'q.go': 'मेरा पुर्ज़ा डिज़ाइन करें', 'q.skip': 'सवाल छोड़ें',
    'done': 'हो गया। आपका पुर्ज़ा तैयार है।',
    'res.part': 'आपका पुर्ज़ा', 'res.ai': 'AI ने शुरू से डिज़ाइन किया', 'res.tpl': 'बना-बनाया पुर्ज़ा, आपके माप का',
    'res.stage': 'आपका पुर्ज़ा बाईं ओर मंच पर है। घुमाने के लिए खींचें।',
    'res.zip': 'सब कुछ डाउनलोड करें (.zip)', 'res.fit': 'फ़िट टेस्ट', 'res.notes': 'प्रिंट नोट्स',
    'res.closed': 'ठोस और बंद', 'res.attn': 'ध्यान चाहिए',
    'res.warn': 'प्रिंट से पहले जाँचें', 'res.assumed': 'माने गए माप। असली वस्तु से मिलाकर देखें।', 'res.how': 'प्रिंट कैसे करें', 'res.fit2': 'फ़िट',
    'res.disc': 'भरोसा करने से पहले टेस्ट प्रिंट करें। प्रिंट किए गए पुर्ज़े हल्के काम की सहायक चीज़ें हैं, सुरक्षा उपकरण नहीं।',
    'tune.title': 'माप बदलें', 'tune.sub': 'बिना AI, कुछ सेकंड', 'tune.go': 'इन मापों से दोबारा बनाएँ',
    'rev.q': 'डिज़ाइन बदलवाना है?', 'rev.ph': 'पकड़ 10 मिमी लंबी करें और किनारे गोल करें।', 'rev.go': 'डिज़ाइन बदलें',
    'est.sliced': '{src} से स्लाइस किया: लगभग {g} ग्राम {m}, प्रिंट में लगभग {min} मिनट।', 'est.rough': 'मोटा अनुमान: लगभग {g} ग्राम {m}, प्रिंट में लगभग {min} मिनट।',
    'o.cached': 'इसी अनुरोध के लिए पहले बन चुका था, इसलिए AI को बुलाना नहीं पड़ा।', 'o.tuned': 'आपके मापों से दोबारा बनाया गया, AI के बिना।', 'o.revised': 'आपके कहे अनुसार बदला गया।',
    'how.one': '{n} डिज़ाइन दौर', 'how.many': '{n} डिज़ाइन दौर', 'how.reviewed': ', अपने ही नतीजे की तस्वीर से जाँचा गया', 'how.by': '। डिज़ाइनर: {m}',
    'hist.btn': 'इतिहास', 'hist.title': 'इतिहास और आँकड़े', 'close': 'बंद करें', 'tab.stats': 'आँकड़े',
    'hist.loading': 'इतिहास लोड हो रहा है…', 'hist.err': 'इतिहास लोड नहीं हो सका। कृपया फिर कोशिश करें।',
    'mic.start': 'टाइप करने की जगह बोलें', 'mic.stop': 'सुनना बंद करें', 'mic.listening': 'सुन रहा हूँ… अब बोलिए।',
    'mic.denied': 'माइक्रोफ़ोन बंद है। ब्राउज़र की सेटिंग में उसे चालू करें, फिर कोशिश करें।',
    'mic.unsupported': 'इस ब्राउज़र में बोलकर लिखना उपलब्ध नहीं है। Chrome, Edge या Safari आज़माएँ।',
    'mic.nospeech': 'कुछ सुनाई नहीं दिया। फिर कोशिश करें।', 'mic.network': 'बोली पहचानने वाली सेवा तक नहीं पहुँच सके। इंटरनेट जाँचें।',
    'mic.nolang': 'इस ब्राउज़र में यह भाषा सुनकर लिखना संभव नहीं। टाइप करें या कोई और भाषा चुनें।'
  },
  kn: {
    'nav.problem': 'ಸಮಸ್ಯೆ', 'nav.how': 'ಇದು ಹೇಗೆ ಕೆಲಸ ಮಾಡುತ್ತದೆ', 'nav.examples': 'ಉದಾಹರಣೆಗಳು', 'nav.start': 'ಹೊಂದಿಸಿ',
    'repair.title': 'ಬಳಸಲು ಯಾವುದು ಕಷ್ಟ ಎಂದು ಹೇಳಿ.',
    'repair.intro': 'ಕೆಲವು ಫೋಟೋಗಳನ್ನು ಕಳುಹಿಸಿ, ಅದನ್ನು ಬಳಸಲು ಸುಲಭ ಮಾಡುವ ಭಾಗವನ್ನು ನಾವು ವಿನ್ಯಾಸ ಮಾಡುತ್ತೇವೆ. AI ಓದುವುದು ಇದನ್ನೇ: 1–3 ಫೋಟೋಗಳು, ಬೇಕಾದರೆ ಅಳತೆಗಳು, ಸಮಸ್ಯೆಯ ವಿವರಣೆ, ಇದು ಯಾರಿಗಾಗಿ, ಮತ್ತು ವಸ್ತುವಿನ ಆದ್ಯತೆ.',
    'drop.b': '1–3 ಫೋಟೋಗಳನ್ನು ಬಿಡಿ', 'drop.rest': ' ಅಥವಾ ಆಯ್ಕೆ ಮಾಡಲು ಟ್ಯಾಪ್ ಮಾಡಿ',
    'what.label': 'ಸಮಸ್ಯೆ ಏನು?', 'what.ph': 'ನನ್ನ ಅಜ್ಜಿಗೆ ನೀರಿನ ಬಾಟಲಿಯ ನಯವಾದ ಮುಚ್ಚಳವನ್ನು ಹಿಡಿಯಲು ಆಗುವುದಿಲ್ಲ.',
    'dims.label': 'ಅಳತೆಗಳು (ಐಚ್ಛಿಕ)', 'dims.ph': 'ಉದಾ. ಕುತ್ತಿಗೆ 50 ಮಿಮೀ',
    'mat.label': 'ವಸ್ತುವಿನ ಆದ್ಯತೆ', 'mat.0': 'ಯಾವುದೂ ಆದ್ಯತೆ ಇಲ್ಲ', 'mat.1': 'ಬಾಳಿಕೆ ಬರುವುದು', 'mat.2': 'ಬಾಗುವ ಮತ್ತು ಹಿಡಿತ ಕೊಡುವ',
    'who.label': 'ಇದು ಯಾರಿಗಾಗಿ?', 'who.0': 'ಯಾರಿಗಾದರೂ', 'who.1': 'ದುರ್ಬಲ ಹಿಡಿತ ಅಥವಾ ಸಂಧಿವಾತ', 'who.2': 'ಕಡಿಮೆ ದೃಷ್ಟಿ ಅಥವಾ ಕುರುಡು', 'who.3': 'ಚಲನೆಯಲ್ಲಿ ಮಿತಿ', 'who.4': 'ಕೈ ನಡುಕ ಅಥವಾ ಬೆರಳುಗಳ ಚಲನೆಯಲ್ಲಿ ಮಿತಿ',
    'submit': 'ಭಾಗಕ್ಕೆ ವಿನಂತಿಸಿ',
    'step.0': 'ಓದುವುದು', 'step.1': 'ವಿನ್ಯಾಸ', 'step.2': 'ಪರಿಶೀಲನೆ', 'step.3': 'ಫೈಲ್‌ಗಳ ತಯಾರಿ',
    'lang.label': 'ಭಾಷೆ',
    'idle': 'ಪ್ರಿಂಟರ್ ಸಿದ್ಧವಿದೆ. ಭಾಗವನ್ನು ವಿವರಿಸಿ, ಇಲ್ಲಿಂದಲೇ ಪ್ರಾರಂಭವಾಗುತ್ತದೆ.',
    'stage.asking': 'ನಿಮ್ಮ ವಿನಂತಿಯನ್ನು ಓದಲಾಗುತ್ತಿದೆ', 'stage.queued': 'ಸರತಿಯಲ್ಲಿದೆ', 'stage.planning': 'ನಿಮ್ಮ ವಿನಂತಿಯನ್ನು ಓದಲಾಗುತ್ತಿದೆ',
    'stage.designing': 'AI ನಿಮ್ಮ ಭಾಗವನ್ನು ವಿನ್ಯಾಸ ಮಾಡುತ್ತಿದೆ. ಇದಕ್ಕೆ ಒಂದೆರಡು ನಿಮಿಷ ಬೇಕಾಗಬಹುದು.',
    'stage.building': 'ಫೈಲ್‌ಗಳನ್ನು ತಯಾರಿಸಿ ಪ್ರಿಂಟ್ ಮಾಡಬಹುದೇ ಎಂದು ಪರಿಶೀಲಿಸಲಾಗುತ್ತಿದೆ', 'stage.working': 'ಕೆಲಸ ನಡೆಯುತ್ತಿದೆ',
    's.write': 'AI ನಿಮ್ಮ ಭಾಗಕ್ಕಾಗಿ CAD ಕೋಡ್ ಬರೆಯುತ್ತಿದೆ', 's.fix': 'AI ವಿನ್ಯಾಸವನ್ನು ಸರಿಪಡಿಸುತ್ತಿದೆ',
    's.approved': 'AI ತನ್ನ ರೆಂಡರ್ ಪರಿಶೀಲಿಸಿ ವಿನ್ಯಾಸವನ್ನು ಅನುಮೋದಿಸಿದೆ',
    's.check': 'ಆಕಾರದ ಪರಿಶೀಲನೆ: ಮುಚ್ಚಿದ ಘನ, ಗೋಡೆಯ ದಪ್ಪ, ಓವರ್‌ಹ್ಯಾಂಗ್',
    's.problem': 'ಸಮಸ್ಯೆ ಸಿಕ್ಕಿದೆ, ಸರಿಪಡಿಸಲು AI ಗೆ ಮರಳಿ ಕಳುಹಿಸಲಾಗುತ್ತಿದೆ', 's.render': 'AI ನೋಡಲು ಭಾಗದ ರೆಂಡರ್ ಮಾಡಲಾಗುತ್ತಿದೆ',
    'note.empty': 'ಮೊದಲು ಬಳಸಲು ಯಾವುದು ಕಷ್ಟ ಎಂದು ಹೇಳಿ.',
    'note.demo': 'ಕೇವಲ ಡೆಮೊ: ಏನನ್ನೂ ಅಪ್‌ಲೋಡ್ ಮಾಡಿಲ್ಲ ಅಥವಾ ಕಳುಹಿಸಿಲ್ಲ. ReForm3D ನಲ್ಲಿ ಈ ಮಾಹಿತಿ ಮೇಲೆ ತೋರಿಸಿದ AI ಪ್ರಕ್ರಿಯೆಗೆ ಹೋಗುತ್ತದೆ.',
    'status.demo': 'ಡೆಮೊ ಮೋಡ್: ಈ ಪುಟಕ್ಕೆ ಯಾವುದೇ ವಿನ್ಯಾಸ ಸರ್ವರ್ ಸಂಪರ್ಕಿಸಿಲ್ಲ.',
    'status.ai': 'ವಿನ್ಯಾಸ ಸರ್ವರ್ ಆನ್‌ಲೈನ್ ಇದೆ. AI ವಿನ್ಯಾಸ ಚಾಲನೆಯಲ್ಲಿದೆ ({m}); ಬ್ಯಾಕಪ್ ಆಗಿ {t} ಸಿದ್ಧ ಭಾಗಗಳಿವೆ.',
    'status.noai': 'ವಿನ್ಯಾಸ ಸರ್ವರ್ ಆನ್‌ಲೈನ್ ಇದೆ, AI ವಿನ್ಯಾಸ ಆಫ್ ಆಗಿದೆ: ವಿನಂತಿಗಳನ್ನು {t} ಸಿದ್ಧ ಭಾಗಗಳೊಂದಿಗೆ ಹೊಂದಿಸಲಾಗುತ್ತದೆ.',
    'status.off': 'ವಿನ್ಯಾಸ ಸರ್ವರ್ ಈಗ ಸಿಗುತ್ತಿಲ್ಲ. ಸರ್ವರ್ ವಿಳಾಸ ಪರಿಶೀಲಿಸಿ, ನಂತರ ಪುಟವನ್ನು ಮರುಲೋಡ್ ಮಾಡಿ.',
    'models': 'ಮಾದರಿಗಳು', 'err.generic': 'ಏನೋ ತಪ್ಪಾಗಿದೆ. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.',
    'q.title': 'ಕೆಲವು ಸಣ್ಣ ಪ್ರಶ್ನೆಗಳು', 'q.sub': 'ಭಾಗ ಸರಿಯಾಗಿ ಹೊಂದಲು. ತಪ್ಪಾದ ಉತ್ತರ ಇದ್ದರೆ ಬದಲಿಸಿ.', 'q.go': 'ನನ್ನ ಭಾಗವನ್ನು ವಿನ್ಯಾಸ ಮಾಡಿ', 'q.skip': 'ಪ್ರಶ್ನೆಗಳನ್ನು ಬಿಟ್ಟುಬಿಡಿ',
    'done': 'ಆಯಿತು. ನಿಮ್ಮ ಭಾಗ ಸಿದ್ಧವಾಗಿದೆ.',
    'res.part': 'ನಿಮ್ಮ ಭಾಗ', 'res.ai': 'AI ಮೊದಲಿನಿಂದ ವಿನ್ಯಾಸ ಮಾಡಿದ್ದು', 'res.tpl': 'ಸಿದ್ಧ ಭಾಗ, ನಿಮ್ಮ ಅಳತೆಗೆ ಹೊಂದಿಸಿದ್ದು',
    'res.stage': 'ನಿಮ್ಮ ಭಾಗ ಎಡಭಾಗದ ವೇದಿಕೆಯಲ್ಲಿದೆ. ತಿರುಗಿಸಲು ಎಳೆಯಿರಿ.',
    'res.zip': 'ಎಲ್ಲವನ್ನೂ ಡೌನ್‌ಲೋಡ್ ಮಾಡಿ (.zip)', 'res.fit': 'ಫಿಟ್ ಟೆಸ್ಟ್', 'res.notes': 'ಪ್ರಿಂಟ್ ಟಿಪ್ಪಣಿಗಳು',
    'res.closed': 'ಮುಚ್ಚಿದ ಘನ', 'res.attn': 'ಗಮನ ಬೇಕು',
    'res.warn': 'ಪ್ರಿಂಟ್ ಮಾಡುವ ಮೊದಲು ಪರಿಶೀಲಿಸಿ', 'res.assumed': 'ಊಹಿಸಿದ ಅಳತೆಗಳು. ನಿಜವಾದ ವಸ್ತುವಿನೊಂದಿಗೆ ಹೋಲಿಸಿ ನೋಡಿ.', 'res.how': 'ಪ್ರಿಂಟ್ ಮಾಡುವುದು ಹೇಗೆ', 'res.fit2': 'ಹೊಂದಾಣಿಕೆ',
    'res.disc': 'ಅವಲಂಬಿಸುವ ಮೊದಲು ಪರೀಕ್ಷಾ ಪ್ರಿಂಟ್ ಮಾಡಿ. ಪ್ರಿಂಟ್ ಮಾಡಿದ ಭಾಗಗಳು ಹಗುರ ಬಳಕೆಯ ಸಹಾಯಕ ವಸ್ತುಗಳು, ಸುರಕ್ಷತಾ ಸಾಧನಗಳಲ್ಲ.',
    'tune.title': 'ಅಳತೆಗಳನ್ನು ಹೊಂದಿಸಿ', 'tune.sub': 'AI ಇಲ್ಲ, ಕೆಲವೇ ಸೆಕೆಂಡುಗಳು', 'tune.go': 'ಈ ಅಳತೆಗಳೊಂದಿಗೆ ಮರುನಿರ್ಮಿಸಿ',
    'rev.q': 'ವಿನ್ಯಾಸ ಬದಲಾಯಿಸಬೇಕೇ?', 'rev.ph': 'ಹಿಡಿಕೆಯನ್ನು 10 ಮಿಮೀ ಉದ್ದ ಮಾಡಿ ಮತ್ತು ಅಂಚುಗಳನ್ನು ದುಂಡಗೆ ಮಾಡಿ.', 'rev.go': 'ವಿನ್ಯಾಸ ಬದಲಿಸಿ',
    'est.sliced': '{src} ನಿಂದ ಸ್ಲೈಸ್ ಮಾಡಲಾಗಿದೆ: ಸುಮಾರು {g} ಗ್ರಾಂ {m}, ಪ್ರಿಂಟ್ ಆಗಲು ಸುಮಾರು {min} ನಿಮಿಷ.', 'est.rough': 'ಸ್ಥೂಲ ಅಂದಾಜು: ಸುಮಾರು {g} ಗ್ರಾಂ {m}, ಪ್ರಿಂಟ್ ಆಗಲು ಸುಮಾರು {min} ನಿಮಿಷ.',
    'o.cached': 'ಇದೇ ವಿನಂತಿಗೆ ಮೊದಲೇ ತಯಾರಿಸಲಾಗಿತ್ತು, ಆದ್ದರಿಂದ AI ಕರೆ ಬೇಕಾಗಲಿಲ್ಲ.', 'o.tuned': 'ನಿಮ್ಮ ಅಳತೆಗಳೊಂದಿಗೆ ಮರುನಿರ್ಮಿಸಲಾಗಿದೆ, AI ಇಲ್ಲದೆ.', 'o.revised': 'ನೀವು ಹೇಳಿದಂತೆ ಬದಲಾಯಿಸಲಾಗಿದೆ.',
    'how.one': '{n} ವಿನ್ಯಾಸ ಪ್ರಯತ್ನ', 'how.many': '{n} ವಿನ್ಯಾಸ ಪ್ರಯತ್ನಗಳು', 'how.reviewed': ', ತನ್ನದೇ ಫಲಿತಾಂಶದ ಚಿತ್ರದೊಂದಿಗೆ ಪರಿಶೀಲಿಸಲಾಗಿದೆ', 'how.by': '. ವಿನ್ಯಾಸಗಾರ: {m}',
    'hist.btn': 'ಇತಿಹಾಸ', 'hist.title': 'ಇತಿಹಾಸ ಮತ್ತು ಅಂಕಿಅಂಶ', 'close': 'ಮುಚ್ಚಿ', 'tab.stats': 'ಅಂಕಿಅಂಶ',
    'hist.loading': 'ಇತಿಹಾಸ ಲೋಡ್ ಆಗುತ್ತಿದೆ…', 'hist.err': 'ಇತಿಹಾಸವನ್ನು ಲೋಡ್ ಮಾಡಲಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.',
    'mic.start': 'ಟೈಪ್ ಮಾಡುವ ಬದಲು ಮಾತನಾಡಿ', 'mic.stop': 'ಕೇಳುವುದನ್ನು ನಿಲ್ಲಿಸಿ', 'mic.listening': 'ಕೇಳುತ್ತಿದೆ… ಈಗ ಮಾತನಾಡಿ.',
    'mic.denied': 'ಮೈಕ್ರೊಫೋನ್ ನಿರ್ಬಂಧಿಸಲಾಗಿದೆ. ಬ್ರೌಸರ್ ಸೆಟ್ಟಿಂಗ್‌ನಲ್ಲಿ ಅನುಮತಿಸಿ, ನಂತರ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.',
    'mic.unsupported': 'ಈ ಬ್ರೌಸರ್‌ನಲ್ಲಿ ಮಾತಿನಿಂದ ಬರೆಯುವ ಸೌಲಭ್ಯವಿಲ್ಲ. Chrome, Edge ಅಥವಾ Safari ಬಳಸಿ.',
    'mic.nospeech': 'ಏನೂ ಕೇಳಿಸಲಿಲ್ಲ. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.', 'mic.network': 'ಮಾತು ಗುರುತಿಸುವ ಸೇವೆಯನ್ನು ತಲುಪಲಾಗಲಿಲ್ಲ. ಇಂಟರ್ನೆಟ್ ಪರಿಶೀಲಿಸಿ.',
    'mic.nolang': 'ಈ ಬ್ರೌಸರ್ ಈ ಭಾಷೆಯನ್ನು ಕೇಳಿ ಬರೆಯಲು ಸಾಧ್ಯವಿಲ್ಲ. ಟೈಪ್ ಮಾಡಿ ಅಥವಾ ಬೇರೆ ಭಾಷೆ ಆರಿಸಿ.'
  },
  ta: {
    'nav.problem': 'பிரச்சினை', 'nav.how': 'செயல்முறை', 'nav.examples': 'எடுத்துக்காட்டு', 'nav.start': 'எளிதாக்கு',
    'repair.title': 'பயன்படுத்த எது கடினமாக உள்ளது என்று சொல்லுங்கள்.',
    'repair.intro': 'சில படங்களை அனுப்புங்கள், அதைப் பயன்படுத்த எளிதாக்கும் பாகத்தை நாங்கள் வடிவமைப்போம். AI படிப்பது இதைத்தான்: 1–3 படங்கள், விருப்பமானால் அளவுகள், பிரச்சினையின் விளக்கம், இது யாருக்காக, மற்றும் பொருள் விருப்பம்.',
    'drop.b': '1–3 படங்களை இழுத்து விடுங்கள்', 'drop.rest': ' அல்லது தேர்வு செய்யத் தட்டுங்கள்',
    'what.label': 'பிரச்சினை என்ன?', 'what.ph': 'என் பாட்டியால் தண்ணீர் பாட்டிலின் வழுவழுப்பான மூடியைப் பிடிக்க முடியவில்லை.',
    'dims.label': 'அளவுகள் (விருப்பம்)', 'dims.ph': 'எ.கா. கழுத்து 50 மிமீ',
    'mat.label': 'பொருள் விருப்பம்', 'mat.0': 'விருப்பம் இல்லை', 'mat.1': 'நீடித்து உழைக்கும்', 'mat.2': 'வளையும், பிடிப்பு தரும்',
    'who.label': 'இது யாருக்காக?', 'who.0': 'யாருக்கும்', 'who.1': 'பலவீனமான பிடிப்பு அல்லது மூட்டுவலி', 'who.2': 'குறைந்த பார்வை அல்லது பார்வையின்மை', 'who.3': 'நடமாட்டத்தில் வரம்பு', 'who.4': 'கை நடுக்கம் அல்லது விரல் இயக்கத்தில் வரம்பு',
    'submit': 'பாகம் கோருங்கள்',
    'step.0': 'படித்தல்', 'step.1': 'வடிவமைத்தல்', 'step.2': 'சரிபார்த்தல்', 'step.3': 'கோப்புகள் உருவாக்கல்',
    'lang.label': 'மொழி',
    'idle': 'பிரிண்டர் தயார். பாகத்தை விவரியுங்கள், இங்கிருந்தே தொடங்கும்.',
    'stage.asking': 'உங்கள் கோரிக்கை படிக்கப்படுகிறது', 'stage.queued': 'வரிசையில் உள்ளது', 'stage.planning': 'உங்கள் கோரிக்கை படிக்கப்படுகிறது',
    'stage.designing': 'AI உங்கள் பாகத்தை வடிவமைக்கிறது. இதற்கு ஒரு நிமிடம் அல்லது இரண்டு ஆகலாம்.',
    'stage.building': 'கோப்புகள் உருவாக்கப்பட்டு, அவை அச்சிடக்கூடியவையா என்று சரிபார்க்கப்படுகிறது', 'stage.working': 'வேலை நடக்கிறது',
    's.write': 'AI உங்கள் பாகத்திற்கான CAD குறியீட்டை எழுதுகிறது', 's.fix': 'AI வடிவமைப்பைச் சரிசெய்கிறது',
    's.approved': 'AI தன் ரெண்டரைச் சரிபார்த்து வடிவமைப்பை ஏற்றுக்கொண்டது',
    's.check': 'வடிவச் சரிபார்ப்பு: மூடிய திடம், சுவர் தடிமன், ஓவர்ஹேங்',
    's.problem': 'சிக்கல் கண்டறியப்பட்டது, சரிசெய்ய AI-க்குத் திருப்பி அனுப்பப்படுகிறது', 's.render': 'AI பார்க்கும்படி பாகத்தின் ரெண்டர் உருவாக்கப்படுகிறது',
    'note.empty': 'முதலில் பயன்படுத்த எது கடினமாக உள்ளது என்று சொல்லுங்கள்.',
    'note.demo': 'டெமோ மட்டும்: எதுவும் பதிவேற்றப்படவோ அனுப்பப்படவோ இல்லை. ReForm3D-ல் இந்த உள்ளீடுகள் மேலே காட்டப்பட்ட AI செயல்முறைக்குச் செல்லும்.',
    'status.demo': 'டெமோ பயன்முறை: இந்தப் பக்கத்துடன் வடிவமைப்பு சர்வர் இணைக்கப்படவில்லை.',
    'status.ai': 'வடிவமைப்பு சர்வர் இயங்குகிறது. AI வடிவமைப்பு இயக்கத்தில் உள்ளது ({m}); காப்புக்காக {t} தயார் பாகங்கள் உள்ளன.',
    'status.noai': 'வடிவமைப்பு சர்வர் இயங்குகிறது, AI வடிவமைப்பு அணைக்கப்பட்டுள்ளது: கோரிக்கைகள் {t} தயார் பாகங்களுடன் பொருத்தப்படும்.',
    'status.off': 'வடிவமைப்பு சர்வரை இப்போது அடைய முடியவில்லை. சர்வர் முகவரியைச் சரிபார்த்து, பக்கத்தை மீண்டும் ஏற்றுங்கள்.',
    'models': 'மாடல்கள்', 'err.generic': 'ஏதோ தவறு நடந்தது. மீண்டும் முயற்சிக்கவும்.',
    'q.title': 'சில சிறு கேள்விகள்', 'q.sub': 'பாகம் சரியாகப் பொருந்த. தவறான பதில் இருந்தால் மாற்றுங்கள்.', 'q.go': 'என் பாகத்தை வடிவமைக்கவும்', 'q.skip': 'கேள்விகளைத் தவிர்க்கவும்',
    'done': 'முடிந்தது. உங்கள் பாகம் தயார்.',
    'res.part': 'உங்கள் பாகம்', 'res.ai': 'AI புதிதாக வடிவமைத்தது', 'res.tpl': 'தயார் பாகம், உங்கள் அளவுக்கு மாற்றப்பட்டது',
    'res.stage': 'உங்கள் பாகம் இடதுபுற மேடையில் உள்ளது. சுழற்ற இழுக்கவும்.',
    'res.zip': 'அனைத்தையும் பதிவிறக்கவும் (.zip)', 'res.fit': 'பொருத்தப் பரிசோதனை', 'res.notes': 'அச்சிடும் குறிப்புகள்',
    'res.closed': 'மூடிய திடம்', 'res.attn': 'கவனம் தேவை',
    'res.warn': 'அச்சிடும் முன் சரிபார்க்கவும்', 'res.assumed': 'கருதப்பட்ட அளவுகள். உண்மையான பொருளுடன் ஒப்பிட்டுப் பாருங்கள்.', 'res.how': 'எப்படி அச்சிடுவது', 'res.fit2': 'பொருத்தம்',
    'res.disc': 'நம்புவதற்கு முன் சோதனை அச்சு எடுங்கள். அச்சிடப்பட்ட பாகங்கள் இலகு பயன்பாட்டு உதவிப் பொருட்கள், பாதுகாப்புக் கருவிகள் அல்ல.',
    'tune.title': 'அளவுகளைச் சரிசெய்யவும்', 'tune.sub': 'AI இல்லை, சில வினாடிகள்', 'tune.go': 'இந்த அளவுகளுடன் மீண்டும் உருவாக்கவும்',
    'rev.q': 'வடிவமைப்பை மாற்ற வேண்டுமா?', 'rev.ph': 'பிடியை 10 மிமீ நீளமாக்கி, ஓரங்களை வட்டமாக்குங்கள்.', 'rev.go': 'வடிவமைப்பை மாற்றவும்',
    'est.sliced': '{src} மூலம் ஸ்லைஸ் செய்யப்பட்டது: சுமார் {g} கிராம் {m}, அச்சிட சுமார் {min} நிமிடம்.', 'est.rough': 'தோராய மதிப்பீடு: சுமார் {g} கிராம் {m}, அச்சிட சுமார் {min} நிமிடம்.',
    'o.cached': 'இதே கோரிக்கைக்கு முன்பே உருவாக்கப்பட்டது, அதனால் AI அழைப்பு தேவைப்படவில்லை.', 'o.tuned': 'உங்கள் அளவுகளுடன் மீண்டும் உருவாக்கப்பட்டது, AI இல்லாமல்.', 'o.revised': 'நீங்கள் கேட்டபடி மாற்றப்பட்டது.',
    'how.one': '{n} வடிவமைப்புச் சுற்று', 'how.many': '{n} வடிவமைப்புச் சுற்றுகள்', 'how.reviewed': ', தன் சொந்த முடிவின் படத்துடன் சரிபார்க்கப்பட்டது', 'how.by': '. வடிவமைத்தது: {m}',
    'hist.btn': 'வரலாறு', 'hist.title': 'வரலாறும் புள்ளிவிவரமும்', 'close': 'மூடு', 'tab.stats': 'புள்ளிவிவரம்',
    'hist.loading': 'வரலாறு ஏற்றப்படுகிறது…', 'hist.err': 'வரலாற்றை ஏற்ற முடியவில்லை. மீண்டும் முயற்சிக்கவும்.',
    'mic.start': 'தட்டச்சுக்குப் பதிலாகப் பேசுங்கள்', 'mic.stop': 'கேட்பதை நிறுத்து', 'mic.listening': 'கேட்கிறது… இப்போது பேசுங்கள்.',
    'mic.denied': 'மைக்ரோஃபோன் தடுக்கப்பட்டுள்ளது. உலாவி அமைப்புகளில் அனுமதித்து, மீண்டும் முயற்சிக்கவும்.',
    'mic.unsupported': 'இந்த உலாவியில் பேசி எழுதும் வசதி இல்லை. Chrome, Edge அல்லது Safari பயன்படுத்தவும்.',
    'mic.nospeech': 'எதுவும் கேட்கவில்லை. மீண்டும் முயற்சிக்கவும்.', 'mic.network': 'பேச்சு அறிதல் சேவையை அடைய முடியவில்லை. இணையத்தைச் சரிபார்க்கவும்.',
    'mic.nolang': 'இந்த உலாவி இந்த மொழியைக் கேட்டு எழுத முடியாது. தட்டச்சு செய்யுங்கள் அல்லது வேறு மொழியைத் தேர்ந்தெடுங்கள்.'
  },
  te: {
    'nav.problem': 'సమస్య', 'nav.how': 'ఇది ఎలా పనిచేస్తుంది', 'nav.examples': 'ఉదాహరణలు', 'nav.start': 'అనువుగా మార్చండి',
    'repair.title': 'వాడటానికి ఏది కష్టంగా ఉందో చెప్పండి.',
    'repair.intro': 'కొన్ని ఫోటోలు పంపండి, దాన్ని వాడటం సులభం చేసే భాగాన్ని మేము డిజైన్ చేస్తాము. AI చదివేది ఇదే: 1–3 ఫోటోలు, కావాలంటే కొలతలు, సమస్య వివరణ, ఇది ఎవరి కోసం, మరియు పదార్థం ప్రాధాన్యత.',
    'drop.b': '1–3 ఫోటోలను వదలండి', 'drop.rest': ' లేదా ఎంచుకోవడానికి నొక్కండి',
    'what.label': 'సమస్య ఏమిటి?', 'what.ph': 'మా అమ్మమ్మ నీళ్ల సీసా నున్నటి మూతను పట్టుకోలేకపోతోంది.',
    'dims.label': 'కొలతలు (ఐచ్ఛికం)', 'dims.ph': 'ఉదా. మెడ 50 మిమీ',
    'mat.label': 'పదార్థం ప్రాధాన్యత', 'mat.0': 'ప్రాధాన్యత లేదు', 'mat.1': 'మన్నికైనది', 'mat.2': 'వంగేది, పట్టు ఇచ్చేది',
    'who.label': 'ఇది ఎవరి కోసం?', 'who.0': 'ఎవరికైనా', 'who.1': 'బలహీనమైన పట్టు లేదా కీళ్లనొప్పులు', 'who.2': 'తక్కువ చూపు లేదా అంధత్వం', 'who.3': 'కదలికలో పరిమితి', 'who.4': 'చేతి వణుకు లేదా వేళ్ల కదలికలో పరిమితి',
    'submit': 'భాగాన్ని కోరండి',
    'step.0': 'చదవడం', 'step.1': 'డిజైన్', 'step.2': 'తనిఖీ', 'step.3': 'ఫైళ్లు తయారు చేయడం',
    'lang.label': 'భాష',
    'idle': 'ప్రింటర్ సిద్ధంగా ఉంది. భాగాన్ని వివరించండి, ఇక్కడే మొదలవుతుంది.',
    'stage.asking': 'మీ అభ్యర్థన చదువుతున్నాం', 'stage.queued': 'క్యూలో ఉంది', 'stage.planning': 'మీ అభ్యర్థన చదువుతున్నాం',
    'stage.designing': 'AI మీ భాగాన్ని డిజైన్ చేస్తోంది. దీనికి ఒకటి రెండు నిమిషాలు పట్టవచ్చు.',
    'stage.building': 'ఫైళ్లు తయారు చేసి, అవి ప్రింట్ అవుతాయో లేదో తనిఖీ చేస్తున్నాం', 'stage.working': 'పని జరుగుతోంది',
    's.write': 'AI మీ భాగానికి CAD కోడ్ రాస్తోంది', 's.fix': 'AI డిజైన్‌ను సరిచేస్తోంది',
    's.approved': 'AI తన రెండర్‌ను పరిశీలించి డిజైన్‌ను ఆమోదించింది',
    's.check': 'ఆకారం తనిఖీ: మూసిన ఘనం, గోడ మందం, ఓవర్‌హ్యాంగ్',
    's.problem': 'సమస్య కనిపించింది, సరిచేయడానికి AIకి తిరిగి పంపుతున్నాం', 's.render': 'AI చూడటానికి భాగం రెండర్ చేస్తున్నాం',
    'note.empty': 'ముందుగా వాడటానికి ఏది కష్టంగా ఉందో చెప్పండి.',
    'note.demo': 'డెమో మాత్రమే: ఏదీ అప్‌లోడ్ చేయలేదు, పంపలేదు. ReForm3Dలో ఈ వివరాలు పైన చూపిన AI ప్రక్రియకు వెళ్తాయి.',
    'status.demo': 'డెమో మోడ్: ఈ పేజీకి డిజైన్ సర్వర్ అనుసంధానం కాలేదు.',
    'status.ai': 'డిజైన్ సర్వర్ ఆన్‌లైన్‌లో ఉంది. AI డిజైన్ ఆన్‌లో ఉంది ({m}); బ్యాకప్‌గా {t} సిద్ధ భాగాలు ఉన్నాయి.',
    'status.noai': 'డిజైన్ సర్వర్ ఆన్‌లైన్‌లో ఉంది, AI డిజైన్ ఆఫ్‌లో ఉంది: అభ్యర్థనలను {t} సిద్ధ భాగాలతో సరిపోలుస్తాం.',
    'status.off': 'డిజైన్ సర్వర్ ఇప్పుడు అందుబాటులో లేదు. సర్వర్ చిరునామా తనిఖీ చేసి, పేజీని మళ్లీ లోడ్ చేయండి.',
    'models': 'మోడళ్లు', 'err.generic': 'ఏదో తప్పు జరిగింది. మళ్లీ ప్రయత్నించండి.',
    'q.title': 'కొన్ని చిన్న ప్రశ్నలు', 'q.sub': 'భాగం సరిగ్గా సరిపోవడానికి. తప్పు సమాధానం ఉంటే మార్చండి.', 'q.go': 'నా భాగాన్ని డిజైన్ చేయండి', 'q.skip': 'ప్రశ్నలను దాటవేయండి',
    'done': 'అయింది. మీ భాగం సిద్ధంగా ఉంది.',
    'res.part': 'మీ భాగం', 'res.ai': 'AI మొదటి నుండి డిజైన్ చేసింది', 'res.tpl': 'సిద్ధ భాగం, మీ కొలతలకు మార్చబడింది',
    'res.stage': 'మీ భాగం ఎడమవైపు వేదికపై ఉంది. తిప్పడానికి లాగండి.',
    'res.zip': 'అన్నీ డౌన్‌లోడ్ చేయండి (.zip)', 'res.fit': 'ఫిట్ టెస్ట్', 'res.notes': 'ప్రింట్ నోట్స్',
    'res.closed': 'మూసిన ఘనం', 'res.attn': 'శ్రద్ధ అవసరం',
    'res.warn': 'ప్రింట్ చేసే ముందు తనిఖీ చేయండి', 'res.assumed': 'ఊహించిన కొలతలు. నిజమైన వస్తువుతో సరిచూడండి.', 'res.how': 'ఎలా ప్రింట్ చేయాలి', 'res.fit2': 'సరిపోవడం',
    'res.disc': 'నమ్ముకునే ముందు టెస్ట్ ప్రింట్ చేయండి. ప్రింట్ చేసిన భాగాలు తేలికపాటి సహాయక వస్తువులు, భద్రతా పరికరాలు కావు.',
    'tune.title': 'కొలతలను సర్దుబాటు చేయండి', 'tune.sub': 'AI లేదు, కొన్ని సెకన్లు', 'tune.go': 'ఈ కొలతలతో మళ్లీ తయారు చేయండి',
    'rev.q': 'డిజైన్ మార్చాలా?', 'rev.ph': 'పట్టును 10 మిమీ పొడవు చేసి, అంచులను గుండ్రంగా చేయండి.', 'rev.go': 'డిజైన్ మార్చండి',
    'est.sliced': '{src}తో స్లైస్ చేయబడింది: సుమారు {g} గ్రాముల {m}, ప్రింట్ కావడానికి సుమారు {min} నిమిషాలు.', 'est.rough': 'సుమారు అంచనా: సుమారు {g} గ్రాముల {m}, ప్రింట్ కావడానికి సుమారు {min} నిమిషాలు.',
    'o.cached': 'ఇదే అభ్యర్థనకు ముందే తయారైంది, కాబట్టి AI కాల్ అవసరం లేదు.', 'o.tuned': 'మీ కొలతలతో మళ్లీ తయారు చేయబడింది, AI లేకుండా.', 'o.revised': 'మీరు చెప్పినట్లు మార్చబడింది.',
    'how.one': '{n} డిజైన్ ప్రయత్నం', 'how.many': '{n} డిజైన్ ప్రయత్నాలు', 'how.reviewed': ', తన స్వంత ఫలితం చిత్రంతో తనిఖీ చేయబడింది', 'how.by': '. డిజైన్ చేసింది: {m}',
    'hist.btn': 'చరిత్ర', 'hist.title': 'చరిత్ర మరియు గణాంకాలు', 'close': 'మూసివేయి', 'tab.stats': 'గణాంకాలు',
    'hist.loading': 'చరిత్ర లోడ్ అవుతోంది…', 'hist.err': 'చరిత్రను లోడ్ చేయలేకపోయాం. దయచేసి మళ్లీ ప్రయత్నించండి.',
    'mic.start': 'టైప్ చేయడానికి బదులు మాట్లాడండి', 'mic.stop': 'వినడం ఆపండి', 'mic.listening': 'వింటోంది… ఇప్పుడు మాట్లాడండి.',
    'mic.denied': 'మైక్రోఫోన్ నిరోధించబడింది. బ్రౌజర్ సెట్టింగ్‌లలో అనుమతించి, మళ్లీ ప్రయత్నించండి.',
    'mic.unsupported': 'ఈ బ్రౌజర్‌లో మాటతో రాసే సౌకర్యం లేదు. Chrome, Edge లేదా Safari వాడండి.',
    'mic.nospeech': 'ఏమీ వినిపించలేదు. మళ్లీ ప్రయత్నించండి.', 'mic.network': 'స్పీచ్ గుర్తింపు సేవను చేరలేకపోయాం. ఇంటర్నెట్ తనిఖీ చేయండి.',
    'mic.nolang': 'ఈ బ్రౌజర్ ఈ భాషను విని రాయలేదు. టైప్ చేయండి లేదా మరో భాష ఎంచుకోండి.'
  }
};

/* The design loop reports what it is doing in English; these are the exact lines the server sends. */
const STEP = [
  ['The AI is writing the CAD code', 's.write'], ['The AI is fixing the design', 's.fix'], ['The AI checked its own render', 's.approved'],
  ['Checking the shape', 's.check'], ['Found a problem', 's.problem'], ['Rendering the part', 's.render']
];

let cur = 'en';
const subs = [];
const saved = () => { try { return localStorage.getItem('rf-lang'); } catch (e) { return null; } };
const find = id => LANGS.find(l => l.id === id);

export const getLang = () => cur;
export const aiLanguage = () => (find(cur) || LANGS[0]).ai;          // '' for English: the server then adds no language line
export const speechLang = () => (find(cur) || LANGS[0]).speech;
export const onLang = fn => { subs.push(fn); };

export function t(key, vars) {
  let s = (T[cur] && T[cur][key]) || T.en[key] || key;
  if (vars) s = s.replace(/\{(\w+)\}/g, (m, k) => (vars[k] == null ? m : vars[k]));
  return s;
}

/** The server's progress line, in the chosen language when it is one of the known lines. */
export function stepText(line) {
  if (!line || cur === 'en') return line;
  const hit = STEP.find(([start]) => line.startsWith(start));
  return hit ? t(hit[1]) : line;
}

/** Translate everything marked data-i18n / data-i18n-ph / data-i18n-aria under root. English is the text the page was written with. */
export function applyI18n(root = document) {
  /* English is whatever the page was written with, remembered the first time an element is seen. */
  const give = (el, slot, read, key) => {
    if (el.dataset[slot] === undefined) el.dataset[slot] = read(el);
    const words = cur !== 'en' && T[cur][key];
    return words || el.dataset[slot];
  };
  root.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = give(el, 'enText', e => e.textContent, el.dataset.i18n); });
  root.querySelectorAll('[data-i18n-ph]').forEach(el => { el.placeholder = give(el, 'enPh', e => e.getAttribute('placeholder') || '', el.dataset.i18nPh); });
  root.querySelectorAll('[data-i18n-aria]').forEach(el => { el.setAttribute('aria-label', give(el, 'enAria', e => e.getAttribute('aria-label') || '', el.dataset.i18nAria)); });
}

function setLang(id, { persist = true } = {}) {
  cur = find(id) ? id : 'en';
  document.documentElement.lang = cur;
  document.documentElement.dataset.script = cur === 'en' ? 'latin' : 'indic';
  if (persist) { try { localStorage.setItem('rf-lang', cur); } catch (e) { /* storage blocked: the choice lasts until reload */ } }
  const hidden = document.getElementById('lang'); if (hidden) hidden.value = aiLanguage();
  const pick = document.getElementById('rfLangPick'); if (pick) pick.value = cur;
  applyI18n();
  subs.forEach(fn => { try { fn(cur); } catch (e) { /* one listener failing must not stop the rest */ } });
  document.dispatchEvent(new CustomEvent('rf-lang', { detail: cur }));
}

/** The shared top-right corner: language picker (here) and the History button (history.js). */
export function topTools() {
  let box = document.getElementById('rfTop');
  if (!box) { box = document.createElement('div'); box.id = 'rfTop'; box.className = 'rf-top'; document.body.append(box); }
  return box;
}

let started = false;
export function initI18n() {
  if (started) return; started = true;
  const wrap = document.createElement('label');
  wrap.className = 'rf-lang';
  wrap.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M3 12h18M12 3c2.6 2.7 3.9 5.7 3.9 9S14.6 18.3 12 21c-2.6-2.7-3.9-5.7-3.9-9S9.4 5.7 12 3z" fill="none" stroke="currentColor" stroke-width="1.7"/></svg>'
    + '<select id="rfLangPick" data-i18n-aria="lang.label" aria-label="Language">' + LANGS.map(l => `<option value="${l.id}" lang="${l.id}">${l.label}</option>`).join('') + '</select>';
  topTools().prepend(wrap);
  const pick = wrap.querySelector('select');
  pick.addEventListener('change', () => setLang(pick.value));
  let first = saved();
  if (!find(first)) { const nav = (navigator.languages || [navigator.language || 'en']).map(l => String(l).slice(0, 2).toLowerCase()).find(l => find(l)); first = nav || 'en'; }
  setLang(first, { persist: false });
}
