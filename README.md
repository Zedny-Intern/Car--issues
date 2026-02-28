# Car Diagnosis System

دليل تشغيل المشروع باستخدام Docker Compose.

## 1. المتطلبات

- Docker Desktop
- Docker Compose
- ملف `.env` صالح

تأكد أن Docker شغال قبل أي خطوة:

```powershell
docker version
docker compose version
```

## 2. الخدمات داخل المشروع

- `frontend`: Nginx + React على المنفذ `80`
- `backend`: Django + Gunicorn
- `celery`: عامل الخلفية للمهام غير المتزامنة
- `db`: PostgreSQL
- `redis`: Redis

## 3. تجهيز المشروع أول مرة

انسخ ملف البيئة:

```powershell
Copy-Item .env.example .env
```

بعدها عدل ملف `.env` وأهم المتغيرات:

```env
SECRET_KEY=change-this
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1
DB_PASSWORD=strong-password
COHERE_API_KEY=your-cohere-key
```

## 4. وضع التشغيل الخفيف الافتراضي

المشروع مضبوط افتراضيًا على وضع خفيف داخل Docker:

- لا يثبت local ML stack الثقيلة إلا إذا طلبت ذلك
- يستخدم Cohere للـ embeddings
- يستخدم fallback خفيف للتصنيف بدل تحميل TensorFlow محليًا

القيم الافتراضية المهمة:

```env
INSTALL_LOCAL_ML=false
INSTALL_OPTIONAL_LLM_FALLBACKS=false
ENABLE_LOCAL_TEXT_EMBEDDINGS=False
ENABLE_LOCAL_CLASSIFIER=False
TEXT_EMBEDDING_BACKEND=cohere
```

إذا أردت تفعيل الـ local ML الثقيل:

```env
INSTALL_LOCAL_ML=true
ENABLE_LOCAL_TEXT_EMBEDDINGS=True
ENABLE_LOCAL_CLASSIFIER=True
```

ثم أعد البناء.

## 5. البناء

بناء كل الصور:

```powershell
docker compose build
```

بناء بدون cache:

```powershell
docker compose build --no-cache
```

بناء خدمة واحدة فقط:

```powershell
docker compose build backend
docker compose build frontend
```

## 6. التشغيل

تشغيل المشروع في الخلفية:

```powershell
docker compose up -d
```

تشغيل مع إعادة بناء:

```powershell
docker compose up -d --build
```

تشغيل ومشاهدة اللوج مباشرة:

```powershell
docker compose up --build
```

## 7. التحقق بعد التشغيل

حالة الخدمات:

```powershell
docker compose ps
```

الواجهة:

```text
http://localhost
```

فحص Nginx health:

```text
http://localhost/health
```

ملاحظة:

- `backend` عليه healthcheck داخلي على `/healthz`
- `frontend` هو المدخل الخارجي الرئيسي

## 8. المراقبة

عرض كل اللوج:

```powershell
docker compose logs -f
```

عرض لوج خدمة معينة:

```powershell
docker compose logs -f backend
docker compose logs -f celery
docker compose logs -f frontend
docker compose logs -f db
docker compose logs -f redis
```

متابعة حالة الحاويات:

```powershell
docker compose ps
```

فحص health status بتفصيل أكبر:

```powershell
docker inspect car_diagnosis_backend --format "{{json .State.Health }}"
docker inspect car_diagnosis_frontend --format "{{json .State.Health }}"
docker inspect car_diagnosis_db --format "{{json .State.Health }}"
docker inspect car_diagnosis_redis --format "{{json .State.Health }}"
```

الدخول داخل الحاوية:

```powershell
docker compose exec backend sh
docker compose exec frontend sh
docker compose exec db sh
docker compose exec redis sh
```

## 9. أوامر تشغيل مهمة داخل backend

تشغيل priming للـ RAG/runtime يدويًا:

```powershell
docker compose exec backend python manage.py prime_runtime
```

تشغيله في الخلفية:

```powershell
docker compose exec backend python manage.py prime_runtime --async
```

تطبيق migrations يدويًا:

```powershell
docker compose exec backend python manage.py migrate
```

جمع الملفات الثابتة:

```powershell
docker compose exec backend python manage.py collectstatic --noinput
```

## 10. إعادة التشغيل

إعادة تشغيل كل الخدمات:

```powershell
docker compose restart
```

إعادة تشغيل خدمة معينة:

```powershell
docker compose restart backend
docker compose restart celery
docker compose restart frontend
```

## 11. الإيقاف

إيقاف الخدمات بدون حذف الحاويات:

```powershell
docker compose stop
```

إيقاف خدمة واحدة:

```powershell
docker compose stop backend
```

إيقاف وحذف الحاويات والشبكة:

```powershell
docker compose down
```

إيقاف مع حذف الـ volumes:

```powershell
docker compose down -v
```

تحذير:

- `docker compose down -v` سيحذف بيانات PostgreSQL وRedis وstatic/media volumes

## 12. إعادة البناء بعد تعديل الإعدادات

إذا عدلت أي شيء في:

- `Dockerfile`
- `requirements`
- `.env` الخاصة بخيارات البناء

نفذ:

```powershell
docker compose down
docker compose build --no-cache
docker compose up -d
```

ولو عدلت فقط كود Python أو React داخل الصور:

```powershell
docker compose up -d --build
```

## 13. تنظيف الصور والكاش

حذف الحاويات المتوقفة والشبكات غير المستخدمة:

```powershell
docker system prune
```

تنظيف أقوى:

```powershell
docker system prune -a
```

حذف volumes غير المستخدمة:

```powershell
docker volume prune
```

## 14. أماكن البيانات المهمة

- بيانات PostgreSQL داخل volume: `postgres_data`
- بيانات Redis داخل volume: `redis_data`
- الملفات الثابتة داخل volume: `static_volume`
- الملفات المرفوعة داخل volume: `media_volume`
- ملفات RAG المحلية على الجهاز: `./data`
- ملفات manuals الثابتة: `./rag data`

## 15. أوامر سريعة مختصرة

تشغيل:

```powershell
docker compose up -d --build
```

مراقبة:

```powershell
docker compose logs -f
```

حالة الخدمات:

```powershell
docker compose ps
```

إيقاف:

```powershell
docker compose down
```

إيقاف مع حذف البيانات:

```powershell
docker compose down -v
```

## 16. ملاحظات مهمة

- الوضع الافتراضي خفيف ويحتاج `COHERE_API_KEY` لكي يعمل الـ RAG بشكل كامل
- لو شغلت `INSTALL_LOCAL_ML=true` ستزيد الصورة بشكل واضح لأن TensorFlow والموديلات المحلية ستدخل في البناء
- بعد أي تغيير في متغيرات build args يجب إعادة `build` وليس `restart` فقط
