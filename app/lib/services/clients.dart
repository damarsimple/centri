import '../config/settings.dart';
import 'measurement_api.dart';
import 'pedagogy_api.dart';

/// Build backend clients from the current [Settings].
extension Clients on Settings {
  MeasurementApi get measurement =>
      MeasurementApi(baseUrl: measurementUrl, apiKey: measurementKey);
  PedagogyApi get pedagogy => PedagogyApi(baseUrl: pedagogyUrl);
}
