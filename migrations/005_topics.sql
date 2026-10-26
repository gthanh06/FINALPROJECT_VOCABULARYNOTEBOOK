-- 005_topics.sql : group words by topic (animals, home & furniture, study...).
-- One topic has many words; a word has at most one topic (NULL = "Chưa phân loại").
-- The list of topics is the same for every user.
CREATE TABLE IF NOT EXISTS topics (
  id       serial PRIMARY KEY,
  slug     text NOT NULL UNIQUE,
  name     text NOT NULL,
  icon     text NOT NULL,
  position integer NOT NULL
);

INSERT INTO topics (slug, name, icon, position) VALUES
('study', 'Học tập & trường lớp', '🎓', 1),
('work', 'Công việc', '💼', 2),
('technology', 'Công nghệ', '💻', 3),
('daily', 'Đời sống hằng ngày', '☀️', 4),
('home', 'Nhà cửa & nội thất', '🛋️', 5),
('animals', 'Con vật', '🐾', 6),
('food', 'Đồ ăn & thức uống', '🍜', 7),
('travel', 'Du lịch', '✈️', 8),
('health', 'Sức khoẻ', '💪', 9),
('environment', 'Môi trường', '🌿', 10),
('feelings', 'Cảm xúc & tính cách', '😊', 11),
('common', 'Từ thông dụng', '⭐', 12),
('academic', 'Học thuật & IELTS', '📊', 13),
('idioms', 'Cụm từ & thành ngữ', '💬', 14)
ON CONFLICT (slug) DO NOTHING;

-- Deleting a topic keeps its words; they just become "Chưa phân loại".
ALTER TABLE words ADD COLUMN IF NOT EXISTS topic_id integer REFERENCES topics (id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS words_topic_id_idx ON words (topic_id);

-- Put the starter words from 003 into their topics, both the starter set (user_id NULL)
-- and the copies users already have. A word a user added themselves stays NULL
-- unless it is also a starter word.
-- Học tập & trường lớp
UPDATE words SET topic_id = (SELECT id FROM topics WHERE slug = 'study')
  WHERE topic_id IS NULL AND lower(word) IN ('achieve', 'assignment', 'curriculum', 'deadline', 'degree', 'diligent', 'enroll', 'graduate', 'knowledge', 'lecture', 'memorize', 'participate', 'research', 'revise', 'scholarship', 'semester', 'thesis', 'tuition', 'comprehend', 'evaluate');
-- Công việc
UPDATE words SET topic_id = (SELECT id FROM topics WHERE slug = 'work')
  WHERE topic_id IS NULL AND lower(word) IN ('applicant', 'colleague', 'negotiate', 'promote', 'resign', 'salary', 'schedule', 'employee', 'interview', 'meeting', 'responsible', 'efficient', 'collaborate', 'delegate', 'feedback', 'candidate', 'contract', 'workload', 'productive');
-- Công nghệ
UPDATE words SET topic_id = (SELECT id FROM topics WHERE slug = 'technology')
  WHERE topic_id IS NULL AND lower(word) IN ('algorithm', 'bandwidth', 'database', 'deploy', 'encrypt', 'framework', 'install', 'interface', 'network', 'repository', 'software', 'update', 'upload', 'virtual', 'automate', 'backup', 'debug', 'feature', 'vulnerability', 'artificial intelligence');
-- Đời sống hằng ngày
UPDATE words SET topic_id = (SELECT id FROM topics WHERE slug = 'daily')
  WHERE topic_id IS NULL AND lower(word) IN ('appointment', 'commute', 'errand', 'grocery', 'household', 'neighbor', 'recipe', 'rent', 'routine', 'chore', 'convenient', 'crowded', 'afford', 'borrow', 'lend', 'bargain', 'refund', 'receipt', 'leftovers', 'nap');
-- Đồ ăn & thức uống
UPDATE words SET topic_id = (SELECT id FROM topics WHERE slug = 'food')
  WHERE topic_id IS NULL AND lower(word) IN ('apple');
-- Du lịch
UPDATE words SET topic_id = (SELECT id FROM topics WHERE slug = 'travel')
  WHERE topic_id IS NULL AND lower(word) IN ('itinerary', 'destination', 'accommodation', 'luggage', 'passport', 'souvenir', 'sightseeing', 'reservation', 'departure', 'delay', 'explore', 'landmark', 'abroad', 'journey', 'budget');
-- Sức khoẻ
UPDATE words SET topic_id = (SELECT id FROM topics WHERE slug = 'health')
  WHERE topic_id IS NULL AND lower(word) IN ('symptom', 'prescription', 'recover', 'nutrition', 'exhausted', 'injury', 'allergic', 'workout', 'stress', 'balanced', 'heal', 'cure', 'insomnia', 'hygiene', 'vaccine');
-- Môi trường
UPDATE words SET topic_id = (SELECT id FROM topics WHERE slug = 'environment')
  WHERE topic_id IS NULL AND lower(word) IN ('pollution', 'recycle', 'climate', 'renewable', 'sustainable', 'emission', 'endangered', 'deforestation', 'conserve', 'habitat', 'drought', 'flood', 'waste', 'environment', 'organic');
-- Cảm xúc & tính cách
UPDATE words SET topic_id = (SELECT id FROM topics WHERE slug = 'feelings')
  WHERE topic_id IS NULL AND lower(word) IN ('anxious', 'confident', 'curious', 'generous', 'grateful', 'honest', 'humble', 'jealous', 'patient', 'reliable', 'stubborn', 'optimistic', 'ambitious', 'embarrassed', 'frustrated', 'overwhelmed', 'relieved', 'thoughtful', 'cheerful', 'nostalgic');
-- Từ thông dụng
UPDATE words SET topic_id = (SELECT id FROM topics WHERE slug = 'common')
  WHERE topic_id IS NULL AND lower(word) IN ('acknowledge', 'adapt', 'avoid', 'consider', 'contribute', 'emphasize', 'encourage', 'estimate', 'hesitate', 'improve', 'maintain', 'postpone', 'prevent', 'recommend', 'require', 'suggest', 'persuade', 'struggle', 'overcome', 'pursue', 'reveal', 'appreciate', 'determine', 'ensure', 'identify', 'abundant', 'accurate', 'affordable', 'brilliant', 'essential', 'flexible', 'obvious', 'reluctant', 'rural', 'urban', 'vivid', 'opportunity', 'priority', 'solution', 'strategy', 'habit', 'community', 'generation', 'tradition', 'advantage', 'persevere');
-- Học thuật & IELTS
UPDATE words SET topic_id = (SELECT id FROM topics WHERE slug = 'academic')
  WHERE topic_id IS NULL AND lower(word) IN ('significant', 'consequence', 'phenomenon', 'hypothesis', 'crucial', 'controversial', 'inevitable', 'substantial', 'approach', 'benefit', 'challenge', 'evidence', 'factor', 'impact', 'perspective', 'trend', 'analyze', 'decline', 'fluctuate', 'dramatically', 'gradually', 'approximately', 'furthermore', 'nevertheless', 'whereas', 'although', 'unless', 'despite', 'regarding', 'throughout');
-- Cụm từ & thành ngữ
UPDATE words SET topic_id = (SELECT id FROM topics WHERE slug = 'idioms')
  WHERE topic_id IS NULL AND lower(word) IN ('give up', 'look forward to', 'figure out', 'run out of', 'put off', 'carry on', 'come up with', 'get along with', 'take care of', 'turn down', 'break the ice', 'piece of cake', 'once in a blue moon', 'under the weather', 'hit the books');

-- New starter words for the topics 003 did not cover.
CREATE TEMP TABLE new_words (word text, meaning_vi text, part_of_speech text, example text,
                             usage_note text, topic text) ON COMMIT DROP;
INSERT INTO new_words VALUES
-- Con vật
('dog', 'con chó', 'noun', 'My dog waits for me at the door.', NULL, 'animals'),
('cat', 'con mèo', 'noun', 'The cat is sleeping on the sofa.', NULL, 'animals'),
('bird', 'con chim', 'noun', 'A bird is singing outside my window.', NULL, 'animals'),
('fish', 'con cá', 'noun', 'We keep two fish in a small tank.', 'Số nhiều thường vẫn là fish', 'animals'),
('rabbit', 'con thỏ', 'noun', 'The rabbit has long ears.', NULL, 'animals'),
('horse', 'con ngựa', 'noun', 'She learned to ride a horse.', 'ride a horse', 'animals'),
('cow', 'con bò (cái)', 'noun', 'Cows give us milk.', 'ox / bull = bò đực', 'animals'),
('pig', 'con lợn, con heo', 'noun', 'The farmer feeds the pigs every morning.', NULL, 'animals'),
('chicken', 'con gà; thịt gà', 'noun', 'Chickens lay eggs.', 'hen = gà mái, rooster = gà trống', 'animals'),
('duck', 'con vịt', 'noun', 'Ducks are swimming in the pond.', NULL, 'animals'),
('buffalo', 'con trâu', 'noun', 'Buffaloes help farmers in the rice fields.', 'Số nhiều: buffaloes', 'animals'),
('tiger', 'con hổ', 'noun', 'The tiger is the largest wild cat.', NULL, 'animals'),
('lion', 'con sư tử', 'noun', 'The lion is called the king of the jungle.', NULL, 'animals'),
('elephant', 'con voi', 'noun', 'Elephants have very good memories.', NULL, 'animals'),
('monkey', 'con khỉ', 'noun', 'The monkey climbed up the tree.', NULL, 'animals'),
('bear', 'con gấu', 'noun', 'Bears sleep through the winter.', NULL, 'animals'),
('snake', 'con rắn', 'noun', 'Some snakes are dangerous.', NULL, 'animals'),
('turtle', 'con rùa', 'noun', 'The sea turtle swam slowly.', 'tortoise = rùa cạn', 'animals'),
('mosquito', 'con muỗi', 'noun', 'Mosquitoes can spread disease.', 'Số nhiều: mosquitoes', 'animals'),
('butterfly', 'con bướm', 'noun', 'A butterfly landed on the flower.', NULL, 'animals'),
('bee', 'con ong', 'noun', 'Bees make honey.', NULL, 'animals'),
('dolphin', 'cá heo', 'noun', 'Dolphins are very intelligent.', NULL, 'animals'),
('shark', 'cá mập', 'noun', 'Sharks have many rows of teeth.', NULL, 'animals'),
('pet', 'thú cưng', 'noun', 'Do you have any pets?', 'keep a pet', 'animals'),
('wild animal', 'động vật hoang dã', 'phrase', 'Wild animals should not be kept as pets.', NULL, 'animals'),
('feed', 'cho ăn', 'verb', 'Please feed the cat before you leave.', 'feed - fed - fed', 'animals'),
-- Nhà cửa & nội thất
('sofa', 'ghế sofa', 'noun', 'We watched TV on the sofa.', '= couch', 'home'),
('armchair', 'ghế bành', 'noun', 'Grandpa reads in his armchair.', NULL, 'home'),
('table', 'cái bàn', 'noun', 'Dinner is on the table.', NULL, 'home'),
('chair', 'cái ghế', 'noun', 'Pull up a chair and sit down.', NULL, 'home'),
('bed', 'cái giường', 'noun', 'I make my bed every morning.', 'make the bed = dọn giường', 'home'),
('wardrobe', 'tủ quần áo', 'noun', 'Hang your coat in the wardrobe.', 'Anh-Mỹ: closet', 'home'),
('bookshelf', 'giá sách', 'noun', 'The bookshelf is full of novels.', 'Số nhiều: bookshelves', 'home'),
('drawer', 'ngăn kéo', 'noun', 'The keys are in the top drawer.', NULL, 'home'),
('cupboard', 'tủ chạn, tủ đựng đồ', 'noun', 'The plates are in the cupboard.', 'Chữ p câm: /ˈkʌbəd/', 'home'),
('mirror', 'cái gương', 'noun', 'She looked at herself in the mirror.', NULL, 'home'),
('curtain', 'rèm cửa', 'noun', 'Close the curtains, please.', 'Thường dùng số nhiều', 'home'),
('carpet', 'tấm thảm', 'noun', 'There is a red carpet in the living room.', 'rug = thảm nhỏ', 'home'),
('pillow', 'cái gối', 'noun', 'I need a softer pillow.', NULL, 'home'),
('blanket', 'cái chăn', 'noun', 'It is cold, take another blanket.', NULL, 'home'),
('lamp', 'cái đèn (bàn, ngủ)', 'noun', 'Turn on the lamp next to the bed.', NULL, 'home'),
('fan', 'cái quạt', 'noun', 'Switch on the fan; it is hot.', NULL, 'home'),
('air conditioner', 'máy điều hoà', 'noun', 'The air conditioner is too loud.', 'Viết tắt: AC', 'home'),
('refrigerator', 'tủ lạnh', 'noun', 'Put the milk in the refrigerator.', 'Thân mật: fridge', 'home'),
('washing machine', 'máy giặt', 'noun', 'The washing machine is broken.', NULL, 'home'),
('microwave', 'lò vi sóng', 'noun', 'Heat the soup in the microwave.', NULL, 'home'),
('sink', 'bồn rửa', 'noun', 'The dishes are in the sink.', NULL, 'home'),
('living room', 'phòng khách', 'noun', 'Guests are waiting in the living room.', NULL, 'home'),
('bedroom', 'phòng ngủ', 'noun', 'My bedroom is upstairs.', NULL, 'home'),
('kitchen', 'nhà bếp', 'noun', 'Mom is cooking in the kitchen.', NULL, 'home'),
('bathroom', 'phòng tắm', 'noun', 'The bathroom is next to my room.', NULL, 'home'),
('furniture', 'đồ nội thất', 'noun', 'We bought new furniture for the flat.', 'Không đếm được: a piece of furniture', 'home'),
-- Đồ ăn & thức uống
('rice', 'cơm, gạo', 'noun', 'Vietnamese people eat rice every day.', 'Không đếm được', 'food'),
('noodle', 'mì, sợi bún/phở', 'noun', 'I had a bowl of beef noodles.', 'Thường dùng số nhiều: noodles', 'food'),
('bread', 'bánh mì', 'noun', 'I buy fresh bread every morning.', 'Không đếm được: a loaf / slice of bread', 'food'),
('vegetable', 'rau củ', 'noun', 'Eat more vegetables.', NULL, 'food'),
('fruit', 'trái cây', 'noun', 'Mangoes are my favorite fruit.', NULL, 'food'),
('beef', 'thịt bò', 'noun', 'Pho is often made with beef.', NULL, 'food'),
('pork', 'thịt lợn', 'noun', 'Grilled pork with rice is delicious.', NULL, 'food'),
('seafood', 'hải sản', 'noun', 'Nha Trang is famous for seafood.', 'Không đếm được', 'food'),
('egg', 'quả trứng', 'noun', 'I had two boiled eggs for breakfast.', NULL, 'food'),
('soup', 'món canh, súp', 'noun', 'This soup is too salty.', NULL, 'food'),
('snack', 'đồ ăn vặt', 'noun', 'I need a quick snack.', NULL, 'food'),
('dessert', 'món tráng miệng', 'noun', 'What would you like for dessert?', 'Hai chữ s; desert = sa mạc', 'food'),
('beverage', 'đồ uống', 'noun', 'Beverages are not included in the price.', 'Trang trọng; = drink', 'food'),
('juice', 'nước ép', 'noun', 'A glass of orange juice, please.', NULL, 'food'),
('delicious', 'ngon', 'adjective', 'This cake is delicious!', NULL, 'food'),
('spicy', 'cay', 'adjective', 'Do you like spicy food?', NULL, 'food'),
('salty', 'mặn', 'adjective', 'The soup is a bit salty.', NULL, 'food'),
('sour', 'chua', 'adjective', 'Lemons taste sour.', NULL, 'food'),
('bitter', 'đắng', 'adjective', 'Black coffee is bitter.', NULL, 'food'),
('sweet', 'ngọt', 'adjective', 'I do not like very sweet drinks.', NULL, 'food'),
('boil', 'luộc, đun sôi', 'verb', 'Boil the water before you drink it.', NULL, 'food'),
('fry', 'chiên, rán', 'verb', 'Fry the onions until golden.', 'fry - fried - fried', 'food'),
('grill', 'nướng (vỉ)', 'verb', 'We grilled fish on the beach.', 'bake = nướng lò', 'food'),
('menu', 'thực đơn', 'noun', 'Could I see the menu, please?', NULL, 'food'),
('order', 'gọi món; đơn hàng', 'verb', 'Are you ready to order?', NULL, 'food'),
('vegetarian', 'người ăn chay; chay', 'noun', 'She has been a vegetarian for years.', NULL, 'food');

-- Into the starter set, so new accounts get them...
INSERT INTO words (user_id, word, meaning_vi, part_of_speech, example, usage_note, topic_id)
SELECT NULL, n.word, n.meaning_vi, n.part_of_speech, n.example, n.usage_note, t.id
FROM new_words n JOIN topics t ON t.slug = n.topic
ON CONFLICT DO NOTHING;

-- ...and into every existing notebook (a word the user already has is left alone).
INSERT INTO words (user_id, word, meaning_vi, part_of_speech, example, usage_note, topic_id)
SELECT u.id, n.word, n.meaning_vi, n.part_of_speech, n.example, n.usage_note, t.id
FROM users u CROSS JOIN new_words n JOIN topics t ON t.slug = n.topic
ON CONFLICT DO NOTHING;
