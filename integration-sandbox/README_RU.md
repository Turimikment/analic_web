# Pesochitsa integratsiy

Uchebnyy modul dlya sistemnogo analitika.

Ideya: student ne uchitsya administrirovat Kafka, Redis ili S3. On uchitsya chitat kontrakty, payloady, logi i ponimat, gde zhivut dannye.

Skvoznoj kejs: sozdanie zakaza.

REST sozdaet zakaz. Baza hranit sostoyanie. Redis keshuet status. Kafka publikuet sobytie. S3 hranit fajl. SOAP otpravlyaet zapros v legacy sluzhbu dostavki. Logi svyazyvayut vse shagi cherez request_id.
