import Foundation
import MapKit

struct Place: Encodable {
    let name: String
    let address: String
    let latitude: Double
    let longitude: Double
}

guard let query = readLine(), !query.isEmpty else { exit(2) }
let request = MKLocalSearch.Request()
request.naturalLanguageQuery = query
request.resultTypes = [.address, .pointOfInterest]

let search = MKLocalSearch(request: request)
search.start { response, error in
    if let error = error as? MKError, error.code == .placemarkNotFound {
        print("[]")
        exit(0)
    }
    guard let response else { exit(3) }

    let places = response.mapItems.prefix(6).compactMap { item -> Place? in
        let coordinate: CLLocationCoordinate2D
        let address: String
        if #available(macOS 26.0, *) {
            coordinate = item.location.coordinate
            address = item.address?.fullAddress ?? ""
        } else {
            coordinate = item.placemark.coordinate
            address = item.placemark.title ?? ""
        }
        guard CLLocationCoordinate2DIsValid(coordinate) else { return nil }
        return Place(
            name: item.name ?? address,
            address: address,
            latitude: coordinate.latitude,
            longitude: coordinate.longitude
        )
    }
    guard let output = try? JSONEncoder().encode(places) else { exit(3) }
    print(String(decoding: output, as: UTF8.self))
    exit(0)
}
RunLoop.main.run()
